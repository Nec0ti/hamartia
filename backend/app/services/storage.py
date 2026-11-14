"""Centralized storage layer for the JSON datastore.

Guarantees:
  * Fault tolerance — missing or empty files get safe defaults; malformed
    collections raise instead of hiding or overwriting student data.
  * Atomic writes — each save writes to a temp file then renames, so a crash
    mid-write can never corrupt an existing file.
  * Thread safety — a per-file lock serializes concurrent access.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, List, TypeVar

T = TypeVar("T", bound=object)
# shortcut: locks are process-local, use SQLite before enabling multiple workers.
_FILE_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


class StorageError(RuntimeError):
    """Raised when the datastore cannot be read or written."""


class StorageService:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    # -- internal helpers ---------------------------------------------------

    def _path(self, filename: str) -> Path:
        return self.data_dir / filename

    def _lock_for(self, filename: str) -> threading.Lock:
        key = str(self._path(filename).resolve())
        with _FILE_LOCKS_GUARD:
            lock = _FILE_LOCKS.get(key)
            if lock is None:
                lock = threading.Lock()
                _FILE_LOCKS[key] = lock
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

    @staticmethod
    def _validate_record(model_cls: type, item: Any) -> Any:
        return model_cls.model_validate(item) if hasattr(model_cls, "model_validate") else model_cls(item)

    @staticmethod
    def _dump_record(item: Any) -> Any:
        return item.model_dump(mode="json") if hasattr(item, "model_dump") else item

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

    def _load_list_unlocked(self, filename: str, model_cls: type) -> List[Any]:
        raw = self._read_raw(filename)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("expected a JSON array")
            return [self._validate_record(model_cls, item) for item in data]
        except (ValueError, TypeError) as exc:
            raise StorageError(f"Cannot read invalid {filename}") from exc

    def load_list(self, filename: str, model_cls: type) -> List[Any]:
        """Load a JSON array of records, validating each against model_cls."""
        with self._lock_for(filename):
            return self._load_list_unlocked(filename, model_cls)

    def save_list(self, filename: str, items: List[Any]) -> None:
        lock = self._lock_for(filename)
        with lock:
            serialized = [self._dump_record(item) for item in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))

    def update_list(self, filename: str, model_cls: type, update: Callable[[List[Any]], bool]) -> bool:
        """Apply and persist a list mutation while holding its file lock."""
        with self._lock_for(filename):
            items = self._load_list_unlocked(filename, model_cls)
            if not update(items):
                return False
            serialized = [self._dump_record(item) for item in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))
            return True

    def append_list(self, filename: str, item: Any, model_cls: type) -> None:
        """Append one validated record without losing concurrent updates."""
        lock = self._lock_for(filename)
        with lock:
            try:
                items = self._load_list_unlocked(filename, model_cls)
            except StorageError as exc:
                raise StorageError(f"Cannot append to invalid {filename}") from exc
            items.append(self._validate_record(model_cls, item))
            serialized = [self._dump_record(record) for record in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))

    # -- typed scalar documents --------------------------------------------

    def load_doc(self, filename: str, model_cls: type):
        """Load a single JSON object, validating against model_cls."""
        raw = self._read_raw(filename)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return model_cls.model_validate(data)
        except (ValueError, TypeError) as exc:
            raise StorageError(f"Cannot read invalid {filename}") from exc

    def save_doc(self, filename: str, model: Any) -> None:
        lock = self._lock_for(filename)
        with lock:
            self._write_atomic(filename, json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False))
