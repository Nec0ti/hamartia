"""Measure seeded persisted topic practice summaries over varied history."""

import argparse
import random
import tempfile
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

from app.core.practice import practice_topic_summaries
from app.models.schemas import ExamScoringProfile, PracticeSession
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, measure, probe_oracle_self_check

SEED = 20261114
TODAY = date(2026, 11, 14)
SUBJECTS = ("Matematik", "Türkçe", "Fizik", "Kimya", "Biyoloji", "Tarih", "Coğrafya", "Felsefe")
PROFILE_FIXTURES = {
    ("legacy-yks", 1): {
        "profile_id": "legacy-yks", "version": 1, "display_name": "YKS (legacy)", "country_label": "Türkiye",
        "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
    },
    ("benchmark-rational", 1): {
        "profile_id": "benchmark-rational", "version": 1, "display_name": "Benchmark rational v1", "country_label": "Fixture",
        "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
    },
    ("benchmark-rational", 2): {
        "profile_id": "benchmark-rational", "version": 2, "display_name": "Benchmark rational v2", "country_label": "Fixture",
        "scoring_rule": {"correct_points": "3/2", "wrong_penalty": "1/3", "blank_points": "1/5"},
    },
}


def _profile_fixture(index):
    # Interleave versions of the same ID throughout the workload; reserve legacy
    # rows too so both the historical and custom profile groups are exercised.
    key = (("legacy-yks", 1), ("benchmark-rational", 1), ("benchmark-rational", 2))[index % 3]
    return ExamScoringProfile(**PROFILE_FIXTURES[key])


def make_sessions(count):
    rng = random.Random(SEED)
    sessions = []
    for index in range(count):
        sessions.append(PracticeSession(
            id=f"set-{index}", date=(TODAY - timedelta(days=rng.randrange(730))).isoformat(),
            subject=SUBJECTS[rng.randrange(len(SUBJECTS))], topic=f"Konu {rng.randrange(160):03d}",
            correct=rng.randrange(26), incorrect=rng.randrange(9), blank=1 + rng.randrange(6),
            duration_minutes=rng.randrange(5, 91), duration_seconds=rng.randrange(60),
            scoring_profile=_profile_fixture(index),
        ))
    sessions[0] = PracticeSession(id="set-0", date=TODAY.isoformat(), subject=" Matematik ", topic=" Boundary ",
                                  correct=0, incorrect=0, blank=6, duration_minutes=1, duration_seconds=59,
                                  scoring_profile=_profile_fixture(0))
    sessions[1] = PracticeSession(id="set-1", date=(TODAY - timedelta(days=729)).isoformat(), subject="matematik", topic="boundary",
                                  correct=1000, incorrect=4, blank=0, duration_minutes=90, duration_seconds=0,
                                  scoring_profile=_profile_fixture(1))
    sessions[2] = PracticeSession(id="set-2", date=TODAY.isoformat(), subject="Türkçe", topic="All correct",
                                  correct=1, incorrect=0, blank=0, duration_minutes=0, duration_seconds=0,
                                  scoring_profile=_profile_fixture(2))
    sessions[3] = PracticeSession(id="set-3", date=(TODAY - timedelta(days=1)).isoformat(), subject="matematik", topic="boundary",
                                  correct=8, incorrect=4, blank=2, duration_minutes=12, duration_seconds=0,
                                  scoring_profile=_profile_fixture(2))
    return sessions


def measure_count(count, repeats):
    sessions = make_sessions(count)
    expected_groups = len({(
        item.scoring_profile.profile_id, item.scoring_profile.version,
        item.subject.strip().casefold(), item.topic.strip().casefold(),
    ) for item in sessions})
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
        shared_custom_topic = [
            row for row in summaries
            if row["subject"].casefold() == "matematik" and row["topic"].casefold() == "boundary"
            and row["scoring_profile"]["profile_id"] == "benchmark-rational"
        ]
        assert [row["scoring_profile"]["version"] for row in shared_custom_topic] == [1, 2]
        assert shared_custom_topic[0]["net"] != shared_custom_topic[1]["net"]
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
            "correctness": "every profile-version/topic aggregate, complete profile snapshot, and ordered trend matches an independent literal-rule oracle",
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
        profile_key = (session.scoring_profile.profile_id, session.scoring_profile.version)
        key = (*profile_key, session.subject.strip().casefold(), session.topic.strip().casefold())
        profile_snapshot = PROFILE_FIXTURES[profile_key]
        group = groups.setdefault(key, {
            "subject": session.subject.strip(), "topic": session.topic.strip(),
            "scoring_profile": profile_snapshot, "rows": [],
        })
        group["rows"].append(session)
    result = []
    for group in groups.values():
        rows = sorted(group.pop("rows"), key=lambda row: (row.date, row.created_at, row.id))
        correct = sum(row.correct for row in rows)
        incorrect = sum(row.incorrect for row in rows)
        blank = sum(row.blank for row in rows)
        answered = correct + incorrect
        rule = group["scoring_profile"]["scoring_rule"]

        def literal_net(row):
            return float(
                row.correct * Fraction(rule["correct_points"])
                - row.incorrect * Fraction(rule["wrong_penalty"])
                + row.blank * Fraction(rule["blank_points"])
            )

        net = sum(literal_net(row) for row in rows)
        group.update({
            "correct": correct, "incorrect": incorrect, "blank": blank,
            "session_count": len(rows), "answered": answered, "net": net,
            "accuracy": correct / answered if answered else None,
            "trend": [{
                "id": row.id, "date": row.date,
                "net": literal_net(row),
                "accuracy": row.correct / (row.correct + row.incorrect) if row.correct + row.incorrect else None,
            } for row in rows],
        })
        result.append(group)
    return sorted(result, key=lambda row: (
        row["subject"].casefold(), row["topic"].casefold(),
        row["scoring_profile"]["profile_id"], row["scoring_profile"]["version"],
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
