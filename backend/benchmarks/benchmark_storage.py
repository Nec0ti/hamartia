"""Measure deterministic local exam-storage throughput; no model is loaded."""

import json
import argparse
import random
import tempfile
import time
from datetime import date
from pathlib import Path

from app.core.progression import progression_summary
from app.models.schemas import Exam, UserStats
from app.services.storage import StorageService
from benchmark_common import emit, measure

SEED = 20261114

def main(count=1000, repeats=7, json_output=None):
    if not 1 <= count <= 1000 or not 3 <= repeats <= 31:
        raise ValueError("count must be 1..1000 and repeats 3..31")
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory() as directory:
        storage = StorageService(Path(directory))
        started = time.perf_counter()
        for index in range(count):
            sectioned = index % 100 == 0
            storage.append_list(
                "exams.json",
                Exam(
                    id=f"exam-{index}", date="2026-11-14",
                    subject="TYT Geneli" if sectioned else rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya")),
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
        warm_read = measure(lambda: _assert_count(storage, count), repeats)
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
        emit({
            "benchmark": "json_exam_storage_sequential_append_stress",
            "seed": SEED,
            "records": count,
            "persisted_json_bytes": (Path(directory) / "exams.json").stat().st_size,
            "sectioned_full_mocks": sectioned_count,
            "append_seconds": round(append_seconds, 4),
            "append_records_per_second": round(count / append_seconds, 2),
            "read_seconds": round(read_seconds, 4),
            "warm_read": warm_read,
            "update_one_seconds": round(update_seconds, 4),
            "delete_one_seconds": round(delete_seconds, 4),
            "document_update_seconds": round(document_update_seconds, 4),
            "progression_seconds": round(progression_seconds, 4),
            "correctness": "append/read/update/delete and progression assertions passed",
            "limitations": "Sequential append rewrites the full growing JSON list (O(n^2)); this is a stress case, not the mixed daily-flow workload.",
        }, json_output)


def _assert_count(storage, count):
    assert len(storage.load_list("exams.json", Exam)) == count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.count, args.repeats, args.json_output)
