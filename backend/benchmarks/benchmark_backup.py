"""Measure seeded backup/validation/restore with valid records and PNG uploads."""

import argparse
import hashlib
import json
import random
import struct
import tempfile
import zlib
from pathlib import Path

from app.models.schemas import Exam, Question
from app.services.backup import create_backup, extract_backup, restore_backup
from benchmark_common import emit, measure

SEED = 20261114


def _png(width, height, rng):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    pixels = b"".join(b"\0" + rng.randbytes(width * 3) for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels, 1)) + chunk(b"IEND", b""))


def main(file_count=24, repeats=3, json_output=None):
    if not 1 <= file_count <= 100 or not 3 <= repeats <= 11:
        raise ValueError("file_count must be 1..100 and repeats 3..11")
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory(prefix="hamartia-backup-bench-") as directory:
        root = Path(directory)
        source = root / "source"
        uploads = source / "uploads"
        uploads.mkdir(parents=True)
        questions = []
        exam = Exam(id="benchmark-exam", date="2026-11-14", subject="Matematik",
                    correct=30, incorrect=5, blank=5)
        (source / "exams.json").write_text(json.dumps([exam.model_dump(mode="json")]), encoding="utf-8")
        for index in range(file_count):
            width, height = ((320, 240), (640, 360), (800, 600))[index % 3]
            name = f"q_{index:04d}.png"
            (uploads / name).write_bytes(_png(width, height, rng))
            questions.append(Question(
                id=f"q-{index}", image_name=name, image_path=f"uploads/{name}",
                ocr_text=f"Seeded photographed question {index}; mixed geometry and algebra text.",
                subject=("Matematik", "Fizik", "Kimya")[index % 3], topic=f"Konu {index % 12}",
            ).model_dump(mode="json"))
        (source / "questions.json").write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")

        archive = root / "backup.zip"
        def export():
            create_backup(source, archive)
            with archive.open("rb") as stream:
                hashlib.file_digest(stream, "sha256")

        export_stats = measure(export, repeats)
        extracted = root / "validated"
        def validate():
            if extracted.exists():
                import shutil
                shutil.rmtree(extracted)
            extract_backup(archive, extracted)
        validation_stats = measure(validate, repeats)
        expected_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in uploads.iterdir()}
        actual_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (extracted / "uploads").iterdir()}
        assert actual_hashes == expected_hashes

        restored = root / "restored"
        def restore():
            if restored.exists():
                import shutil
                shutil.rmtree(restored)
            restore_backup(archive, restored)
        restore_stats = measure(restore, repeats)
        assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (restored / "uploads").iterdir()} == expected_hashes
        emit({
            "benchmark": "local_backup_restore", "seed": SEED,
            "files": file_count, "upload_bytes": sum(path.stat().st_size for path in uploads.iterdir()),
            "archive_bytes": archive.stat().st_size,
            "export": export_stats, "validation": validation_stats, "restore": restore_stats,
            "correctness": "all upload hashes and record validation passed",
            "limitations": "Synthetic seeded PNG pixels and metadata; no personal files or full live user corpus.",
        }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.files, args.repeats, args.json_output)
