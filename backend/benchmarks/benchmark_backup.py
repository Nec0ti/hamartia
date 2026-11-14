"""Measure seeded backup/validation/restore with valid records and PNG uploads."""

import argparse
import hashlib
import json
import random
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from app.models.schemas import Exam, Question, Settings
from app.services.backup import create_backup, extract_backup, restore_backup
from benchmark_common import emit, measure, seeded_png

SEED = 20261114


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
        source_settings = Settings(model_name="benchmark/offline", api_key="source-key-not-exported")
        (source / "settings.json").write_text(json.dumps(source_settings.model_dump(mode="json")), encoding="utf-8")
        for index in range(file_count):
            width, height = ((256, 256), (512, 384), (1024, 768))[index % 3]
            name = f"q_{index:04d}.png"
            (uploads / name).write_bytes(seeded_png(width, height, rng))
            questions.append(Question(
                id=f"q-{index}", image_name=name, image_path=f"uploads/{name}",
                ocr_text=f"Seeded photographed question {index}; mixed geometry and algebra text.",
                subject=("Matematik", "Fizik", "Kimya")[index % 3], topic=f"Konu {index % 12}",
            ).model_dump(mode="json"))
        (source / "questions.json").write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")

        archive = root / "backup.zip"
        def export():
            create_backup(source, archive)

        export_stats = measure(export, repeats)
        extracted = root / "validated"
        def validate():
            if extracted.exists():
                shutil.rmtree(extracted)
            extract_backup(archive, extracted)
        validation_stats = measure(validate, repeats)
        expected_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in uploads.iterdir()}
        actual_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (extracted / "uploads").iterdir()}
        assert actual_hashes == expected_hashes

        restored = root / "restored"
        restore_samples = []
        snapshot = None
        for _ in range(repeats + 1):
            if restored.exists():
                shutil.rmtree(restored)
            for old_snapshot in root.glob("restored.before-restore-*"):
                shutil.rmtree(old_snapshot)
            restored.mkdir()
            sentinel_exam = [{"id": "pre-restore", "date": "2026-11-14", "subject": "Before",
                              "correct": 1, "incorrect": 0, "blank": 0}]
            (restored / "exams.json").write_text(json.dumps(sentinel_exam), encoding="utf-8")
            (restored / "settings.json").write_text(json.dumps(Settings(api_key="keep-this-key").model_dump(mode="json")), encoding="utf-8")
            started = time.perf_counter()
            result = restore_backup(archive, restored)
            restore_samples.append(time.perf_counter() - started)
            snapshot = Path(result["snapshot"])
            assert snapshot.is_dir()
            assert json.loads((snapshot / "exams.json").read_text(encoding="utf-8")) == sentinel_exam
            assert Settings.model_validate_json((snapshot / "settings.json").read_bytes()).api_key == "keep-this-key"
            assert json.loads((restored / "exams.json").read_text(encoding="utf-8")) == json.loads((source / "exams.json").read_text(encoding="utf-8"))
            assert json.loads((restored / "questions.json").read_text(encoding="utf-8")) == json.loads((source / "questions.json").read_text(encoding="utf-8"))
            restored_settings = Settings.model_validate_json((restored / "settings.json").read_bytes())
            expected_settings = Settings.model_validate_json((source / "settings.json").read_bytes()).model_dump(mode="json")
            expected_settings["api_key"] = "keep-this-key"
            assert restored_settings.model_dump(mode="json") == expected_settings
        ordered = sorted(restore_samples[1:])
        restore_stats = {
            "samples": repeats,
            "p50_seconds": round(statistics.median(restore_samples[1:]), 6),
            "p95_seconds": round(ordered[max(0, (repeats * 95 + 99) // 100 - 1)], 6),
        }
        assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (restored / "uploads").iterdir()} == expected_hashes
        emit({
            "benchmark": "local_backup_restore", "seed": SEED,
            "files": file_count, "upload_bytes": sum(path.stat().st_size for path in uploads.iterdir()),
            "archive_bytes": archive.stat().st_size,
            "export": export_stats, "validation": validation_stats, "restore": restore_stats,
            "restore_snapshot": "pre-existing data was snapshotted and preserved each run",
            "correctness": "upload hashes and restored exams/questions/settings matched expected values",
            "limitations": "Synthetic seeded PNG pixels and metadata; no personal files or full live user corpus.",
        }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.files, args.repeats, args.json_output)
