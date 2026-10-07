"""Centralized storage layer for the JSON datastore.

Guarantees:
  * Fault tolerance — missing, empty or malformed files degrade to safe
    defaults instead of raising.
  * Atomic writes — each save writes to a temp file then renames, so a crash
    mid-write can never corrupt an existing file.
  * Thread safety — a per-file lock serializes concurrent access.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, List, Type, TypeVar

T = TypeVar("T", bound=object)


class StorageError(RuntimeError):
    """Raised when the datastore cannot be read or written."""


class StorageService:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # One lock per file name keeps operations for different files from
        # blocking each other while still serializing access to the same file.
        self._locks: dict[str, threading.Lock] = {}
        self._lock_guard = threading.Lock()

    # -- internal helpers ---------------------------------------------------

    def _path(self, filename: str) -> Path:
        return self.data_dir / filename

    def _lock_for(self, filename: str) -> threading.Lock:
        with self._lock_guard:
            lock = self._locks.get(filename)
            if lock is None:
                lock = threading.Lock()
                self._locks[filename] = lock
            return lock

    def _read_raw(self, filename: str) -> str:
        path = self._path(filename)
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StorageError(f"Cannot read {filename}: {exc}") from exc
        # Empty or whitespace-only file -> safe default.
        if not content:
            return ""
        return content

    def _write_atomic(self, filename: str, payload: str) -> None:
        path = self._path(filename)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(path)
        except OSError as exc:
            raise StorageError(f"Cannot write {filename}: {exc}") from exc
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # -- typed list collections --------------------------------------------

    def load_list(self, filename: str, model_cls: type) -> List[Any]:
        """Load a JSON array of records, validating each against model_cls."""
        raw = self._read_raw(filename)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            return [model_cls.model_validate(item) for item in data]
        except (ValueError, TypeError):
            # Malformed JSON or incompatible records -> start fresh.
            return []

    def save_list(self, filename: str, items: List[Any]) -> None:
        lock = self._lock_for(filename)
        with lock:
            serialized = [item.model_dump(mode="json") for item in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))

    # -- typed scalar documents --------------------------------------------

    def load_doc(self, filename: str, model_cls: type):
        """Load a single JSON object, validating against model_cls."""
        raw = self._read_raw(filename)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        return model_cls.model_validate(data)

    def save_doc(self, filename: str, model: Any) -> None:
        lock = self._lock_for(filename)
        with lock:
            self._write_atomic(filename, json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False))
