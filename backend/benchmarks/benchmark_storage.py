"""Measure deterministic local exam-storage throughput; no model is loaded."""

import json
import argparse
import random
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

from app.core.progression import progression_summary
from app.models.schemas import Exam, UserStats
from app.services.storage import StorageError, StorageService
from benchmark_common import assert_oracle, emit, measure, probe_oracle_self_check

SEED = 20261114
LEGACY_YKS_SNAPSHOT = {
    "profile_id": "legacy-yks", "version": 1,
    "display_name": "YKS (legacy)", "country_label": "Türkiye",
    "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
}

def main(count=1000, repeats=7, json_output=None):
    if not repeats + 2 <= count <= 1000 or not 3 <= repeats <= 11:
        raise ValueError("count must be repeats+2..1000 and repeats 3..11")
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory() as directory:
        storage = StorageService(Path(directory))
        expected = []
        append_records = []
        for index in range(count):
            sectioned = index % 100 == 0
            correct, incorrect, blank = ((0, 0, 0) if index == 2 else
                                         (1 + index % 31, 1 + index % 7, index % 4))
            exam_date = (date(2026, 11, 14) - timedelta(days=index)).isoformat() if index < 3 else "2025-11-14"
            subject = "TYT Geneli" if sectioned else rng.choice(("Matematik", "Türkçe", "Fizik", "Kimya"))
            sections = ([
                {"subject": "Türkçe", "correct": correct // 2, "incorrect": incorrect // 2, "blank": blank // 2},
                {"subject": "Matematik", "correct": correct - correct // 2, "incorrect": incorrect - incorrect // 2, "blank": blank - blank // 2},
            ] if sectioned else [])
            record = {
                "id": f"exam-{index}", "date": exam_date,
                "subject": subject, "exam_type": "tyt" if sectioned else "branch",
                "correct": correct, "incorrect": incorrect, "blank": blank,
                "total": correct + incorrect,
                "net": correct - incorrect / 4,
                "xp": max(0, int((correct - incorrect / 4) * correct * 1.5
                                 - (1 if index == 3 else 1 + index % 180) * incorrect * 0.25)),
                "scoring_profile": LEGACY_YKS_SNAPSHOT,
                "duration_minutes": (0 if index == 3 else 1 + index % 180),
                "duration_seconds": index % 60, "created_at": "", "sections": sections,
            }
            expected.append(record)
            append_records.append(Exam(**record))
        started = time.perf_counter()
        for item in append_records:
            storage.append_list("exams.json", item, Exam)
        append_seconds = time.perf_counter() - started

        started = time.perf_counter()
        loaded = storage.load_list("exams.json", Exam)
        read_seconds = time.perf_counter() - started
        assert_oracle([item.model_dump(mode="json") for item in loaded], expected, "storage append/read records")
        sectioned_count = sum(bool(exam.sections) for exam in loaded)
        assert sectioned_count == (count + 99) // 100
        warm_read = measure(lambda: storage.load_list("exams.json", Exam), repeats)
        assert len(storage.load_list("exams.json", Exam)) == count
        def update_first(exams):
            exam = next((item for item in exams if item.id == "exam-0"), None)
            if exam is None:
                return False
            exam.duration_minutes += 1
            return True
        update_stats = measure(lambda: storage.update_list("exams.json", Exam, update_first), repeats)
        updated = storage.load_list("exams.json", Exam)
        expected_duration = expected[0]["duration_minutes"] + repeats + 1  # warmup plus measured samples
        expected_after_update = [dict(item) for item in expected]
        expected_after_update[0]["duration_minutes"] = expected_duration
        expected_after_update[0]["xp"] = _record_xp(expected_after_update[0])
        assert_oracle([item.model_dump(mode="json") for item in updated], expected_after_update,
                      "storage full state after update")

        delete_ids = [f"exam-{index}" for index in range(count - 1, count - repeats - 2, -1)]
        delete_stats = measure(lambda: storage.update_list("exams.json", Exam, _delete_callback(delete_ids.pop())), repeats)
        remaining = storage.load_list("exams.json", Exam)
        deleted = {f"exam-{index}" for index in range(count - repeats - 1, count)}
        expected_after_delete = [item for item in expected_after_update if item["id"] not in deleted]
        assert_oracle([item.model_dump(mode="json") for item in remaining], expected_after_delete,
                      "storage full state after delete")

        def add_xp(user):
            user.total_xp += 1
            return True

        document_stats = measure(lambda: storage.update_doc("user.json", UserStats, add_xp), repeats)
        expected_user = {
            "total_xp": repeats + 1, "level": 1, "streak_days": 1,
            "last_active_date": "2026-10-07",
            "radar_stats": {"speed": 50, "focus": 50, "precision": 50, "stamina": 50},
        }
        assert_oracle(storage.load_doc("user.json", UserStats).model_dump(mode="json"), expected_user,
                      "storage full user document")

        progression_stats = measure(lambda: progression_summary(
            storage.load_list("exams.json", Exam), today=date(2026, 11, 14)), repeats)
        progression = progression_summary(storage.load_list("exams.json", Exam), today=date(2026, 11, 14))
        progression_expected = _expected_progression(expected_after_update, set(deleted))
        assert_oracle(progression, progression_expected, "storage progression")
        oracle_self_checks = [probe_oracle_self_check(
            progression, progression_expected,
            lambda output: output.__setitem__("total_xp", output["total_xp"] + 1),
            "progression XP off by one",
        )]
        exams_path = Path(directory) / "exams.json"
        valid_payload = exams_path.read_bytes()
        exams_path.write_text('[{"id":', encoding="utf-8")
        try:
            storage.load_list("exams.json", Exam)
        except StorageError:
            pass
        else:
            raise AssertionError("truncated JSON was accepted as a valid collection")
        assert exams_path.read_text(encoding="utf-8") == '[{"id":'
        exams_path.write_bytes(valid_payload)
        assert len(storage.load_list("exams.json", Exam)) == count - repeats - 1
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
            "oracle_self_checks": oracle_self_checks,
            "corrupt_input_cases": ["truncated JSON rejected without overwriting source"],
            "limitations": "Sequential append rewrites the full growing JSON list (O(n^2)); this is a stress case, not the mixed daily-flow workload.",
        }, json_output)


def _delete_callback(question_id):
    def delete(exams):
        for index, exam in enumerate(exams):
            if exam.id == question_id:
                exams.pop(index)
                return True
        return False
    return delete


def _expected_progression(records, deleted):
    active = [row for row in records if row["id"] not in deleted]
    xp = 0
    days = set()
    for row in active:
        xp += _record_xp(row)
        days.add(date.fromisoformat(row["date"]))
    today = date(2026, 11, 14)
    last = max((day for day in days if day <= today), default=None)
    streak = 0
    if last and last >= today - timedelta(days=1):
        while last - timedelta(days=streak) in days:
            streak += 1
    return {
        "total_xp": xp,
        "level": xp // 500 + 1 if xp >= 500 else 1,
        "streak_days": streak,
        "last_active_date": last.isoformat() if last else "",
    }


def _record_xp(row):
    duration = row["duration_minutes"] or 1
    net = row["correct"] - row["incorrect"] / 4
    return max(0, int(net * row["correct"] * 1.5 - duration * row["incorrect"] * 0.25))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.count, args.repeats, args.json_output)
