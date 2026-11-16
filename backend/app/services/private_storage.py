"""Owner-only permissions for local application data on POSIX systems."""

import os
import stat
from pathlib import Path


def secure_directory(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def secure_data_tree(path: Path) -> None:
    """Restrict existing regular data files and directories without following links."""
    root = Path(path)
    if not root.exists():
        return
    secure_directory(root)
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories[:]:
            child = Path(current) / name
            if child.is_symlink():
                directories.remove(name)
            else:
                secure_directory(child)
        for name in files:
            child = Path(current) / name
            if os.name == "posix" and not child.is_symlink() and stat.S_ISREG(child.stat().st_mode):
                os.chmod(child, 0o600)


def open_private_file(path: Path, flags: int) -> int:
    """Open a new/replaced data file with owner-only mode on POSIX."""
    if os.name == "posix":
        flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if os.name == "posix":
            os.fchmod(descriptor, 0o600)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise
