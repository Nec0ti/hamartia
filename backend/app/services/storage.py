"""Centralized storage layer for the JSON datastore.

Guarantees:
  * Fault tolerance — missing or empty files get safe defaults; malformed
    collections raise instead of hiding or overwriting student data.
  * Atomic writes — each save writes to a temp file then renames, so a crash
    mid-write can never corrupt an existing file.
  * Thread/process safety — mutations serialize across threads and processes.
"""

from __future__ import annotations

import json
import errno
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, List, TypeVar

from app.services.private_storage import open_private_file, secure_directory

T = TypeVar("T", bound=object)
# shortcut: locks are process-local, use SQLite before enabling multiple workers.
_FILE_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()
_DATA_MUTATION_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_MUTATION_DEPTH = threading.local()


def data_mutation_lock(data_dir: Path) -> threading.RLock:
    """Return the process-wide mutation lock shared by a data directory."""
    key = str(Path(data_dir).resolve())
    with _FILE_LOCKS_GUARD:
        lock = _DATA_MUTATION_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _DATA_MUTATION_LOCKS[key] = lock
        return lock


@contextmanager
def _process_mutation_lock(data_dir: Path):
    canonical_dir = Path(data_dir).resolve()
    path = canonical_dir.with_name(f".{canonical_dir.name}.mutation.lock")
    key = str(canonical_dir)
    depths = getattr(_PROCESS_MUTATION_DEPTH, "by_directory", None)
    if depths is None:
        depths = _PROCESS_MUTATION_DEPTH.by_directory = {}
    if depths.get(key, 0):
        depths[key] += 1
        try:
            yield
        finally:
            depths[key] -= 1
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        if os.name == "nt":
            import msvcrt
            lock_file.seek(0)
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EDEADLK) and getattr(exc, "winerror", None) not in (33, 36):
                        raise StorageError(f"Cannot lock data directory {data_dir}: {exc}") from exc
                    time.sleep(0.05)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    break
                except OSError as exc:
                    if exc.errno != errno.EINTR:
                        raise StorageError(f"Cannot lock data directory {data_dir}: {exc}") from exc
        try:
            depths[key] = 1
            yield
        finally:
            depths.pop(key, None)
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _mutation_locks(data_dir: Path):
    with data_mutation_lock(data_dir), _process_mutation_lock(data_dir):
        yield


@contextmanager
def data_mutation_guard(data_dir: Path):
    """Serialize a multi-file operation against local and other-process writes."""
    with _mutation_locks(data_dir):
        yield


class StorageError(RuntimeError):
    """Raised when the datastore cannot be read or written."""


class StorageService:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        from app.services.backup import recover_restore
        recover_restore(self.data_dir)
        secure_directory(self.data_dir)
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
        try:
            if path.is_symlink():
                raise StorageError(f"Cannot read {filename}: symbolic links are not allowed in the data directory")
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
        except FileNotFoundError:
            return ""
        except StorageError:
            raise
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
            descriptor = open_private_file(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
            with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
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
        with _mutation_locks(self.data_dir), self._lock_for(filename):
            serialized = [self._dump_record(item) for item in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))

    def update_list(self, filename: str, model_cls: type, update: Callable[[List[Any]], bool]) -> bool:
        """Apply and persist a list mutation while holding its file lock."""
        with _mutation_locks(self.data_dir), self._lock_for(filename):
            items = self._load_list_unlocked(filename, model_cls)
            if not update(items):
                return False
            serialized = [self._dump_record(item) for item in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))
            return True

    def append_list(self, filename: str, item: Any, model_cls: type) -> None:
        """Append one validated record without losing concurrent updates."""
        with _mutation_locks(self.data_dir), self._lock_for(filename):
            try:
                items = self._load_list_unlocked(filename, model_cls)
            except StorageError as exc:
                raise StorageError(f"Cannot append to invalid {filename}") from exc
            items.append(self._validate_record(model_cls, item))
            serialized = [self._dump_record(record) for record in items]
            self._write_atomic(filename, json.dumps(serialized, indent=2, ensure_ascii=False))

    # -- typed scalar documents --------------------------------------------

    def _load_doc_unlocked(self, filename: str, model_cls: type):
        raw = self._read_raw(filename)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return model_cls.model_validate(data)
        except (ValueError, TypeError) as exc:
            raise StorageError(f"Cannot read invalid {filename}") from exc

    def load_doc(self, filename: str, model_cls: type):
        """Load a single JSON object, validating against model_cls."""
        with self._lock_for(filename):
            return self._load_doc_unlocked(filename, model_cls)

    def update_doc(self, filename: str, model_cls: type, update: Callable[[Any], bool]) -> bool:
        """Apply and persist a document mutation while holding its file lock."""
        with _mutation_locks(self.data_dir), self._lock_for(filename):
            model = self._load_doc_unlocked(filename, model_cls) or model_cls()
            if not update(model):
                return False
            self._write_atomic(filename, json.dumps(self._dump_record(model), indent=2, ensure_ascii=False))
            return True

    def save_doc(self, filename: str, model: Any) -> None:
        with _mutation_locks(self.data_dir), self._lock_for(filename):
            self._write_atomic(filename, json.dumps(model.model_dump(mode="json"), indent=2, ensure_ascii=False))
