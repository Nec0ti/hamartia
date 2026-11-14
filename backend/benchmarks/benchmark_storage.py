"""Measure deterministic local exam-storage throughput; no model is loaded."""

import json
import tempfile
import time
from pathlib import Path

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
                    correct=25, incorrect=5, blank=0, duration_minutes=40,
                ),
                Exam,
            )
        append_seconds = time.perf_counter() - started

        started = time.perf_counter()
        loaded = storage.load_list("exams.json", Exam)
        read_seconds = time.perf_counter() - started
        assert len(loaded) == count
        print(json.dumps({
            "benchmark": "json_exam_storage",
            "records": count,
            "append_seconds": round(append_seconds, 4),
            "append_records_per_second": round(count / append_seconds, 2),
            "read_seconds": round(read_seconds, 4),
            "ai_included": False,
        }))


if __name__ == "__main__":
    main()
