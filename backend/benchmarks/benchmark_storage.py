"""Measure deterministic local exam-storage throughput; no model is loaded."""

import json
import tempfile
import time
from datetime import date
from pathlib import Path

from app.core.progression import progression_summary
from app.models.schemas import Exam, UserStats
from app.services.storage import StorageService


def main(count=1000):
    with tempfile.TemporaryDirectory() as directory:
        storage = StorageService(Path(directory))
        started = time.perf_counter()
        for index in range(count):
            sectioned = index % 100 == 0
            storage.append_list(
                "exams.json",
                Exam(
                    id=f"exam-{index}", date="2026-11-14",
                    subject="TYT Geneli" if sectioned else "Matematik",
                    exam_type="tyt" if sectioned else "branch",
                    correct=25, incorrect=5, blank=0, duration_minutes=40,
                    sections=[
                        {"subject": "Türkçe", "correct": 12, "incorrect": 2, "blank": 0},
                        {"subject": "Matematik", "correct": 13, "incorrect": 3, "blank": 0},
                    ] if sectioned else [],
                ),
                Exam,
            )
        append_seconds = time.perf_counter() - started

        started = time.perf_counter()
        loaded = storage.load_list("exams.json", Exam)
        read_seconds = time.perf_counter() - started
        assert len(loaded) == count
        sectioned_count = sum(bool(exam.sections) for exam in loaded)
        assert sectioned_count == (count + 99) // 100
        started = time.perf_counter()
        def update_first(exams):
            exam = next((item for item in exams if item.id == "exam-0"), None)
            if exam is None:
                return False
            exam.duration_minutes += 1
            return True
        assert storage.update_list("exams.json", Exam, update_first)
        update_seconds = time.perf_counter() - started
        assert storage.load_list("exams.json", Exam)[0].duration_minutes == 41

        started = time.perf_counter()
        assert storage.update_list("exams.json", Exam, lambda exams: exams.pop() is not None)
        delete_seconds = time.perf_counter() - started
        assert len(storage.load_list("exams.json", Exam)) == count - 1

        started = time.perf_counter()
        def add_xp(user):
            user.total_xp += 1
            return True

        storage.update_doc("user.json", UserStats, add_xp)
        document_update_seconds = time.perf_counter() - started
        assert storage.load_doc("user.json", UserStats).total_xp == 1

        started = time.perf_counter()
        progression = progression_summary(loaded, today=date(2026, 11, 14))
        progression_seconds = time.perf_counter() - started
        assert progression["streak_days"] == 1
        print(json.dumps({
            "benchmark": "json_exam_storage",
            "records": count,
            "sectioned_full_mocks": sectioned_count,
            "append_seconds": round(append_seconds, 4),
            "append_records_per_second": round(count / append_seconds, 2),
            "read_seconds": round(read_seconds, 4),
            "update_one_seconds": round(update_seconds, 4),
            "delete_one_seconds": round(delete_seconds, 4),
            "document_update_seconds": round(document_update_seconds, 4),
            "progression_seconds": round(progression_seconds, 4),
            "ai_included": False,
        }))


if __name__ == "__main__":
    main()
