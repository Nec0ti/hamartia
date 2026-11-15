"""Measure seeded backup/validation/restore with valid records and PNG uploads."""

import argparse
import hashlib
import json
import random
import shutil
import statistics
import tempfile
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

from app.models.schemas import Exam, PracticeSession, Question, Settings
from app.services.backup import BackupError, create_backup, extract_backup, restore_backup
from benchmark_common import assert_oracle, emit, measure, probe_oracle_self_check, seeded_photo_png, seeded_png

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
        exam_count = min(400, max(24, file_count * 4))
        exams = []
        for index in range(exam_count):
            sectioned = index % 5 == 0
            sections = ([
                {"subject": "Türkçe", "correct": 30, "incorrect": 7, "blank": 3},
                {"subject": "Matematik", "correct": 27, "incorrect": 8, "blank": 5},
                {"subject": "Fen", "correct": 13, "incorrect": 4, "blank": 3},
                {"subject": "Sosyal", "correct": 15, "incorrect": 3, "blank": 2},
            ] if sectioned else [])
            exams.append(Exam(
                id=f"exam-{index}", date=(date(2026, 11, 14) - timedelta(days=index * 7 % 730)).isoformat(),
                subject="TYT Geneli" if sectioned else ("Matematik", "Türkçe", "Fizik", "Kimya")[index % 4],
                exam_type="tyt" if sectioned else "branch",
                correct=sum(row["correct"] for row in sections) if sectioned else 20 + index % 31,
                incorrect=sum(row["incorrect"] for row in sections) if sectioned else 1 + index % 12,
                blank=sum(row["blank"] for row in sections) if sectioned else index % 6,
                duration_minutes=0 if index == 1 else 45 + index % 100, sections=sections,
            ))
        expected_exams = [exam.model_dump(mode="json") for exam in exams]
        (source / "exams.json").write_text(json.dumps(expected_exams), encoding="utf-8")
        sessions = [PracticeSession(
            id=f"session-{index}", date=(date(2026, 11, 14) - timedelta(days=index * 5 % 730)).isoformat(),
            subject=("Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji")[index % 5],
            topic=("Konu 00" if index % 3 else f"Konu {index % 40:02d}"),
            correct=index % 26, incorrect=index % 8, blank=1 + index % 5,
            duration_minutes=0 if index == 0 else 5 + index % 90, duration_seconds=index % 60,
        ) for index in range(file_count * 4)]
        expected_sessions = [session.model_dump(mode="json") for session in sessions]
        (source / "practice_sessions.json").write_text(json.dumps(expected_sessions, ensure_ascii=False), encoding="utf-8")
        source_settings = Settings(model_name="benchmark/offline", api_key="source-key-not-exported")
        (source / "settings.json").write_text(json.dumps(source_settings.model_dump(mode="json")), encoding="utf-8")
        expected_questions = []
        branch_exams = [exam for exam in exams if not exam.sections]
        for index in range(file_count):
            width, height = ((320, 240), (512, 384), (1024, 768), (1280, 960))[index % 4]
            name = f"q_{index:04d}.png"
            payload = seeded_photo_png(width, height, rng) if index % 3 == 0 else seeded_png(width, height, rng)
            (uploads / name).write_bytes(payload)
            question = Question(
                id=f"q-{index}", image_name=name, image_path=f"uploads/{name}",
                exam_id=branch_exams[index].id if index < min(5, file_count, len(branch_exams)) else "",
                question_number=index + 1 if index < 5 else None,
                solve_order=(5 - index) if index < 5 else None,
                time_spent_seconds=(1 if index == 0 else 30 + index) if index < 5 else None,
                ocr_text=f"Seeded photographed question {index}; mixed geometry and algebra text.",
                subject=branch_exams[index].subject if index < 5 else ("Fizik", "Kimya", "Biyoloji")[index % 3],
                topic=f"Konu {index % 12}",
                review_attempts=[{"attempted_at": "2026-11-13T09:00:00Z", "attempt_day": "2026-11-13", "correct": False},
                                 {"attempted_at": "2026-11-14T09:00:00Z", "attempt_day": "2026-11-14", "correct": index % 2 == 0}] if index < 2 else [],
            )
            expected_questions.append(question.model_dump(mode="json"))
            questions.append(question.model_dump(mode="json"))
        exam_by_id = {exam.id: exam for exam in exams}
        for question in (Question.model_validate(row) for row in questions if row["exam_id"]):
            exam = exam_by_id[question.exam_id]
            assert not exam.sections and question.subject == exam.subject
            assert question.question_number <= exam.correct + exam.incorrect + exam.blank
            assert question.solve_order <= exam.correct + exam.incorrect + exam.blank
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
        assert Settings.model_validate_json((extracted / "settings.json").read_bytes()).api_key == ""
        assert_oracle(json.loads((extracted / "exams.json").read_text(encoding="utf-8")),
                      expected_exams, "backup extracted exam history")
        assert_oracle(json.loads((extracted / "practice_sessions.json").read_text(encoding="utf-8")),
                      expected_sessions, "backup extracted practice history")
        assert_oracle(json.loads((extracted / "questions.json").read_text(encoding="utf-8")),
                      expected_questions, "backup extracted questions")

        # Failure-safety fixture: preserve the existing target if a checksummed
        # archive member is corrupted. This is correctness-only, not timed.
        restored = root / "restored"
        restored.mkdir()
        sentinel_exam = [{"id": "keep-me", "date": "2026-11-14", "subject": "Before",
                          "correct": 3, "incorrect": 2, "blank": 1}]
        (restored / "exams.json").write_text(json.dumps(sentinel_exam), encoding="utf-8")
        (restored / "settings.json").write_text(json.dumps(Settings(api_key="keep-this-key").model_dump(mode="json")), encoding="utf-8")
        corrupt_archive = root / "corrupt-member.zip"
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(corrupt_archive, "w", zipfile.ZIP_DEFLATED) as changed:
            for entry in original.infolist():
                payload = original.read(entry.filename)
                if entry.filename == "uploads/q_0000.png":
                    payload = payload[:-1] + bytes([payload[-1] ^ 1])
                changed.writestr(entry.filename, payload)
        snapshots_before = set(root.glob("restored.before-restore-*"))
        try:
            restore_backup(corrupt_archive, restored)
        except BackupError:
            pass
        else:
            raise AssertionError("restore accepted a ZIP member with a wrong manifest digest")
        assert_oracle(json.loads((restored / "exams.json").read_text(encoding="utf-8")),
                      sentinel_exam,
                      "failed restore preserves previous target")
        assert Settings.model_validate_json((restored / "settings.json").read_bytes()).api_key == "keep-this-key"
        assert set(root.glob("restored.before-restore-*")) == snapshots_before

        unsafe_archive = root / "unsafe-path.zip"
        with zipfile.ZipFile(unsafe_archive, "w") as archive_file:
            archive_file.writestr("../escape-marker.txt", "must not escape extraction root")
        try:
            extract_backup(unsafe_archive, root / "unsafe-extracted")
        except BackupError:
            pass
        else:
            raise AssertionError("backup extractor accepted a path traversal member")
        assert not (root / "escape-marker.txt").exists()

        broken_source = root / "broken-reference-source"
        shutil.copytree(source, broken_source)
        broken_records = json.loads((broken_source / "questions.json").read_text(encoding="utf-8"))
        broken_records[0]["image_path"] = "uploads/missing.png"
        (broken_source / "questions.json").write_text(json.dumps(broken_records), encoding="utf-8")
        broken_archive = root / "broken-reference.zip"
        try:
            create_backup(broken_source, broken_archive)
        except BackupError:
            pass
        else:
            raise AssertionError("backup accepted a missing referenced upload")
        assert not broken_archive.exists()

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
            assert json.loads((restored / "practice_sessions.json").read_text(encoding="utf-8")) == expected_sessions
            assert json.loads((restored / "exams.json").read_text(encoding="utf-8")) == expected_exams
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
        oracle_self_checks = [probe_oracle_self_check(
            json.loads((restored / "questions.json").read_text(encoding="utf-8")),
            expected_questions,
            lambda rows: rows.pop(),
            "backup omitted one question",
        )]
        emit({
            "benchmark": "local_backup_restore", "seed": SEED,
            "files": file_count, "record_counts": {"exams": exam_count, "questions": file_count,
                                                      "practice_sessions": len(sessions)},
            "upload_bytes": sum(path.stat().st_size for path in uploads.iterdir()),
            "upload_size_range_bytes": [min(path.stat().st_size for path in uploads.iterdir()),
                                        max(path.stat().st_size for path in uploads.iterdir())],
            "archive_bytes": archive.stat().st_size,
            "export": export_stats, "validation": validation_stats, "restore": restore_stats,
            "restore_snapshot": "pre-existing data was snapshotted and preserved each run",
            "correctness": "upload hashes and restored exam/question/practice/settings values matched expected values",
            "failure_safety": "checksum-corrupt restore preserved target; missing upload references and ZIP traversal paths were rejected",
            "oracle_self_checks": oracle_self_checks,
            "limitations": "Seeded synthetic image pixels and metadata; no personal files or full live user corpus.",
        }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.files, args.repeats, args.json_output)
