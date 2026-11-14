"""Cross-process lock shared by the API and offline data maintenance tools."""

import os
from pathlib import Path


class DataDirectoryBusy(RuntimeError):
    """Raised when another Hamartia process owns the data directory."""


class DataDirectoryLock:
    def __init__(self, data_dir: Path):
        data_dir = Path(data_dir)
        self.path = data_dir.with_name(f".{data_dir.name}.lock")
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"\0")
            self.file.flush()
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise DataDirectoryBusy(f"Hamartia data directory is in use: {self.path}") from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.file:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None
