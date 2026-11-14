"""Safe resolution of question-image paths within the local upload folder."""

from pathlib import Path, PurePosixPath


class UnsafeUploadPath(ValueError):
    """Raised when an upload path crosses a symbolic link or data boundary."""


def resolve_upload_root(data_dir: Path, *, create: bool = False) -> Path:
    data_dir = Path(data_dir)
    data_root = data_dir.resolve()
    upload_root = data_dir / "uploads"
    if upload_root.is_symlink():
        raise UnsafeUploadPath("Question uploads directory must not be a symbolic link")
    if create:
        upload_root.mkdir(parents=True, exist_ok=True)
    resolved = upload_root.resolve()
    expected = data_root / "uploads"
    if resolved != expected:
        raise UnsafeUploadPath("Question uploads directory is outside the data folder")
    return resolved


def resolve_question_image(data_dir: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise UnsafeUploadPath("Invalid question image path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or relative.as_posix() != value or len(relative.parts) < 2 or relative.parts[0] != "uploads" or ".." in relative.parts:
        raise UnsafeUploadPath("Invalid question image path")

    data_dir = Path(data_dir)
    upload_root = resolve_upload_root(data_dir)
    candidate = data_dir.joinpath(*relative.parts)
    current = data_dir
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise UnsafeUploadPath("Question image path must not contain a symbolic link")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(upload_root):
        raise UnsafeUploadPath("Question image path is outside the uploads directory")
    return candidate
