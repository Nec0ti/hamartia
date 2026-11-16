"""Owner-only permissions for local application data on POSIX systems."""

import os
import stat
from pathlib import Path


def secure_directory(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise OSError(f"Refusing to use symbolic-link directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)
    return path


def secure_data_tree(path: Path) -> None:
    """Restrict existing data and fail closed if the tree contains a symbolic link."""
    root = Path(path)
    if root.is_symlink():
        raise OSError(f"Refusing to use symbolic-link data directory: {root}")
    if not root.exists():
        return
    secure_directory(root)
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories[:]:
            child = Path(current) / name
            if child.is_symlink():
                raise OSError(f"Refusing symbolic-link data directory: {child}")
            else:
                secure_directory(child)
        for name in files:
            child = Path(current) / name
            if child.is_symlink():
                raise OSError(f"Refusing symbolic-link data file: {child}")
            if os.name == "posix" and stat.S_ISREG(child.stat().st_mode):
                if os.chmod in os.supports_follow_symlinks:
                    os.chmod(child, 0o600, follow_symlinks=False)
                else:
                    descriptor = os.open(child, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                    try:
                        os.fchmod(descriptor, 0o600)
                    finally:
                        os.close(descriptor)


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
