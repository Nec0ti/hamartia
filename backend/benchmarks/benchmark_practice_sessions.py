"""Measure seeded persisted topic practice summaries over varied history."""

import argparse
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path

from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession
from app.services.storage import StorageService
from benchmark_common import emit, measure

SEED = 20261114
TODAY = date(2026, 11, 14)
SUBJECTS = ("Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji", "Tarih", "Coğrafya", "Felsefe")


def make_sessions(count):
    rng = random.Random(SEED)
    return [PracticeSession(
        id=f"set-{index}", date=(TODAY - timedelta(days=rng.randrange(730))).isoformat(),
        subject=SUBJECTS[rng.randrange(len(SUBJECTS))], topic=f"Konu {rng.randrange(160):03d}",
        correct=rng.randrange(26), incorrect=rng.randrange(9), blank=1 + rng.randrange(6),
        duration_minutes=rng.randrange(5, 91), duration_seconds=rng.randrange(60),
    ) for index in range(count)]


def measure_count(count, repeats):
    sessions = make_sessions(count)
    expected_groups = len({(item.subject.casefold(), item.topic.casefold()) for item in sessions})
    with tempfile.TemporaryDirectory(prefix="hamartia-practice-bench-") as directory:
        storage = StorageService(Path(directory))
        storage.save_list("practice_sessions.json", sessions)
        def summarize():
            saved = storage.load_list("practice_sessions.json", PracticeSession)
            return practice_topic_summaries(saved)
        summaries = summarize()
        assert sum(group["session_count"] for group in summaries) == count
        assert len(summaries) == expected_groups
        return {
            "sessions": count, "topics": expected_groups,
            "persisted_bytes": (storage.data_dir / "practice_sessions.json").stat().st_size,
            "first_full_summary_seconds": measure(summarize, 1, warmups=0)["p50_seconds"],
            "warm_full_summary": measure(summarize, repeats),
            "correctness": "all sessions and topic groups accounted for",
        }


def main(repeats=7, json_output=None):
    if not 3 <= repeats <= 31:
        raise ValueError("repeats must be between 3 and 31")
    emit({"benchmark": "topic_practice_sessions", "seed": SEED,
          "runs": [measure_count(count, repeats) for count in (1000, 10000)]}, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
