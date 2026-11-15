"""Measure seeded persisted topic practice summaries over varied history."""

import argparse
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, measure, probe_oracle_self_check

SEED = 20261114
TODAY = date(2026, 11, 14)
SUBJECTS = ("Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji", "Tarih", "Coğrafya", "Felsefe")


def make_sessions(count):
    rng = random.Random(SEED)
    sessions = []
    for index in range(count):
        sessions.append(PracticeSession(
            id=f"set-{index}", date=(TODAY - timedelta(days=rng.randrange(730))).isoformat(),
            subject=SUBJECTS[rng.randrange(len(SUBJECTS))], topic=f"Konu {rng.randrange(160):03d}",
            correct=rng.randrange(26), incorrect=rng.randrange(9), blank=1 + rng.randrange(6),
            duration_minutes=rng.randrange(5, 91), duration_seconds=rng.randrange(60),
        ))
    sessions[0] = PracticeSession(id="set-0", date=TODAY.isoformat(), subject=" Matematik ", topic=" Boundary ",
                                  correct=0, incorrect=0, blank=6, duration_minutes=1, duration_seconds=59)
    sessions[1] = PracticeSession(id="set-1", date=(TODAY - timedelta(days=729)).isoformat(), subject="matematik", topic="boundary",
                                  correct=1000, incorrect=4, blank=0, duration_minutes=90, duration_seconds=0)
    sessions[2] = PracticeSession(id="set-2", date=TODAY.isoformat(), subject="Türkçe", topic="All correct",
                                  correct=1, incorrect=0, blank=0, duration_minutes=0, duration_seconds=0)
    return sessions


def measure_count(count, repeats):
    sessions = make_sessions(count)
    expected_groups = len({(item.subject.strip().casefold(), item.topic.strip().casefold()) for item in sessions})
    with tempfile.TemporaryDirectory(prefix="hamartia-practice-bench-") as directory:
        storage = StorageService(Path(directory))
        storage.save_list("practice_sessions.json", sessions)
        def summarize():
            saved = storage.load_list("practice_sessions.json", PracticeSession)
            return practice_topic_summaries(saved)
        summaries = summarize()
        expected = _oracle(sessions)
        assert len(summaries) == expected_groups
        assert_oracle(summaries, expected, "practice full summary")
        oracle_self_checks = [probe_oracle_self_check(
            summaries, expected,
            lambda rows: rows[0].__setitem__("net", rows[0]["net"] + 1),
            "practice net corrupted",
        )]
        return {
            "sessions": count, "topics": expected_groups,
            "persisted_bytes": (storage.data_dir / "practice_sessions.json").stat().st_size,
            "first_full_summary_seconds": measure(summarize, 1, warmups=0)["p50_seconds"],
            "warm_full_summary": measure(summarize, repeats),
            "correctness": "every topic aggregate and ordered trend matches an independent oracle",
            "oracle_self_checks": oracle_self_checks,
        }


def main(repeats=7, json_output=None):
    if not 3 <= repeats <= 31:
        raise ValueError("repeats must be between 3 and 31")
    emit({"benchmark": "topic_practice_sessions", "seed": SEED,
          "runs": [measure_count(count, repeats) for count in (1000, 10000)]}, json_output)


def _oracle(sessions):
    groups = {}
    for session in sessions:
        key = (session.subject.strip().casefold(), session.topic.strip().casefold())
        group = groups.setdefault(key, {"subject": session.subject.strip(), "topic": session.topic.strip(), "rows": []})
        group["rows"].append(session)
    result = []
    for group in groups.values():
        rows = sorted(group.pop("rows"), key=lambda row: (row.date, row.created_at, row.id))
        correct = sum(row.correct for row in rows)
        incorrect = sum(row.incorrect for row in rows)
        blank = sum(row.blank for row in rows)
        answered = correct + incorrect
        net = sum(row.correct for row in rows) - sum(row.incorrect for row in rows) / 4
        group.update({
            "correct": correct, "incorrect": incorrect, "blank": blank,
            "session_count": len(rows), "answered": answered, "net": net,
            "accuracy": correct / answered if answered else None,
            "trend": [{
                "id": row.id, "date": row.date,
                "net": row.correct - row.incorrect / 4,
                "accuracy": row.correct / (row.correct + row.incorrect) if row.correct + row.incorrect else None,
            } for row in rows],
        })
        result.append(group)
    return sorted(result, key=lambda row: (row["subject"].casefold(), row["topic"].casefold()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
