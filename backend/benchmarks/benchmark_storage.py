"""Measure deterministic local exam-storage throughput; no model is loaded."""

import json
import tempfile
import time
from datetime import date
from pathlib import Path

from app.core.progression import progression_summary
from app.models.schemas import Exam
from app.services.storage import StorageService


def main(count=1000):
    with tempfile.TemporaryDirectory() as directory:
        storage = StorageService(Path(directory))
        started = time.perf_counter()
        for index in range(count):
            storage.append_list(
                "exams.json",
                Exam(
                    id=f"exam-{index}", date="2026-11-14", subject="Matematik",
                    exam_type="branch",
                    correct=25, incorrect=5, blank=0, duration_minutes=40,
                ),
                Exam,
            )
        append_seconds = time.perf_counter() - started

        started = time.perf_counter()
        loaded = storage.load_list("exams.json", Exam)
        read_seconds = time.perf_counter() - started
        assert len(loaded) == count
        started = time.perf_counter()
        def update_first(exams):
            exam = next((item for item in exams if item.id == "exam-0"), None)
            if exam is None:
                return False
            exam.subject = "Fizik"
            return True
        assert storage.update_list("exams.json", Exam, update_first)
        update_seconds = time.perf_counter() - started
        assert storage.load_list("exams.json", Exam)[0].subject == "Fizik"

        started = time.perf_counter()
        assert storage.update_list("exams.json", Exam, lambda exams: exams.pop() is not None)
        delete_seconds = time.perf_counter() - started
        assert len(storage.load_list("exams.json", Exam)) == count - 1

        started = time.perf_counter()
        progression = progression_summary(loaded, today=date(2026, 11, 14))
        progression_seconds = time.perf_counter() - started
        assert progression["streak_days"] == 1
        print(json.dumps({
            "benchmark": "json_exam_storage",
            "records": count,
            "append_seconds": round(append_seconds, 4),
            "append_records_per_second": round(count / append_seconds, 2),
            "read_seconds": round(read_seconds, 4),
            "update_one_seconds": round(update_seconds, 4),
            "delete_one_seconds": round(delete_seconds, 4),
            "progression_seconds": round(progression_seconds, 4),
            "ai_included": False,
        }))


if __name__ == "__main__":
    main()
