"""Measure local ZIP backup, validation and restore; no model is loaded."""

import json
import os
import tempfile
import time
from pathlib import Path

from app.services.backup import create_backup, extract_backup, restore_backup


def main(file_count=50, bytes_per_file=2 * 1024 * 1024):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        uploads = source / "uploads"
        uploads.mkdir(parents=True)
        for index in range(file_count):
            (uploads / f"sample-{index}.bin").write_bytes(os.urandom(bytes_per_file))

        archive = root / "backup.zip"
        started = time.perf_counter()
        create_backup(source, archive)
        export_seconds = time.perf_counter() - started

        extracted = root / "validated"
        started = time.perf_counter()
        extract_backup(archive, extracted)
        validation_seconds = time.perf_counter() - started
        assert sum(path.stat().st_size for path in (extracted / "uploads").iterdir()) == file_count * bytes_per_file

        restored = root / "restored"
        started = time.perf_counter()
        restore_backup(archive, restored)
        restore_seconds = time.perf_counter() - started
        assert len(list((restored / "uploads").iterdir())) == file_count
        print(json.dumps({
            "benchmark": "local_backup_restore",
            "files": file_count,
            "upload_bytes": file_count * bytes_per_file,
            "archive_bytes": archive.stat().st_size,
            "export_seconds": round(export_seconds, 4),
            "validation_seconds": round(validation_seconds, 4),
            "restore_seconds": round(restore_seconds, 4),
            "ai_included": False,
        }))


if __name__ == "__main__":
    main()
