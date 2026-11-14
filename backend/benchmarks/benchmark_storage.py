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
    if not repeats + 2 <= count <= 1000 or not 3 <= repeats <= 11:
        raise ValueError("count must be repeats+2..1000 and repeats 3..11")
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
        def update_first(exams):
            exam = next((item for item in exams if item.id == "exam-0"), None)
            if exam is None:
                return False
            exam.duration_minutes += 1
            return True
        update_stats = measure(lambda: _assert_updated(storage, update_first), repeats)
        assert storage.load_list("exams.json", Exam)[0].duration_minutes == 41 + repeats

        delete_ids = [f"exam-{index}" for index in range(count - 1, count - repeats - 2, -1)]
        delete_stats = measure(lambda: _delete_one(storage, delete_ids.pop()), repeats)
        assert len(storage.load_list("exams.json", Exam)) == count - repeats - 1

        def add_xp(user):
            user.total_xp += 1
            return True

        document_stats = measure(lambda: _assert_doc_updated(storage, add_xp), repeats)
        assert storage.load_doc("user.json", UserStats).total_xp == repeats + 1

        progression_stats = measure(lambda: progression_summary(
            storage.load_list("exams.json", Exam), today=date(2026, 11, 14)), repeats)
        progression = progression_summary(loaded, today=date(2026, 11, 14))
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
            "update_one": update_stats,
            "delete_one": delete_stats,
            "document_update": document_stats,
            "progression_full_history": progression_stats,
            "correctness": "append/read/update/delete and progression assertions passed",
            "limitations": "Sequential append rewrites the full growing JSON list (O(n^2)); this is a stress case, not the mixed daily-flow workload.",
        }, json_output)


def _assert_count(storage, count):
    assert len(storage.load_list("exams.json", Exam)) == count


def _assert_updated(storage, update):
    assert storage.update_list("exams.json", Exam, update)


def _delete_one(storage, question_id):
    def delete(exams):
        for index, exam in enumerate(exams):
            if exam.id == question_id:
                exams.pop(index)
                return True
        return False
    assert storage.update_list("exams.json", Exam, delete)


def _assert_doc_updated(storage, update):
    assert storage.update_doc("user.json", UserStats, update)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.count, args.repeats, args.json_output)
