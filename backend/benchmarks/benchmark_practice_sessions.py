"""Measure topic-set persistence and trend summaries; no model is loaded."""

import json
import tempfile
import time
from pathlib import Path

from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession
from app.services.storage import StorageService


def measure(count):
    sessions = [PracticeSession(
        id=f"set-{index}", date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
        subject="Matematik", topic=f"Konu {index % 20}",
        correct=index % 20 + 1, incorrect=index % 4, blank=index % 3,
        duration_minutes=20,
    ) for index in range(count)]
    started = time.perf_counter()
    summaries = practice_topic_summaries(sessions)
    summary_seconds = time.perf_counter() - started
    assert sum(group["session_count"] for group in summaries) == count

    with tempfile.TemporaryDirectory() as directory:
        storage = StorageService(Path(directory))
        started = time.perf_counter()
        storage.save_list("practice_sessions.json", sessions)
        write_seconds = time.perf_counter() - started
        started = time.perf_counter()
        loaded = storage.load_list("practice_sessions.json", PracticeSession)
        read_seconds = time.perf_counter() - started
        assert len(loaded) == count
    return {
        "sessions": count,
        "topics": len(summaries),
        "summary_seconds": round(summary_seconds, 6),
        "write_seconds": round(write_seconds, 6),
        "read_seconds": round(read_seconds, 6),
    }


if __name__ == "__main__":
    print(json.dumps({
        "benchmark": "topic_practice_sessions",
        "runs": [measure(1_000), measure(10_000)],
        "ai_included": False,
    }))
