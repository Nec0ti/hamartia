"""AI-free benchmark for the strict, quote-grounded Study Agent CLI."""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

from app.hamartia_cli import run_json_line

SEED = 20261115

def fixture(index: int) -> tuple[dict, dict]:
    subjects = ("Mathematics", "Physics", "Biology", "History")
    topics = ("Functions", "Motion", "Cells", "Chronology")
    subject = subjects[index % len(subjects)]
    topic = topics[index % len(topics)]
    date = f"2026-11-{index % 28 + 1:02d}"
    correct = index % 18
    incorrect = index % 6
    blank = index % 4
    if correct + incorrect + blank == 0:
        blank = 1
    minutes = 10 + index % 70
    seconds = index % 60
    message = (
        f"I completed a practice test on {topic} in {subject} on {date}. "
        f"I got {correct} right, {incorrect} wrong, left {blank} blank; "
        f"it took {minutes} minutes and {seconds} seconds."
    )
    evidence = [
        {"field": "subject", "quote": f"in {subject}"},
        {"field": "topic", "quote": f"on {topic}"},
        {"field": "date", "quote": f"on {date}"},
        {"field": "correct", "quote": f"{correct} right"},
        {"field": "incorrect", "quote": f"{incorrect} wrong"},
        {"field": "blank", "quote": f"left {blank} blank"},
        {"field": "duration_minutes", "quote": f"{minutes} minutes"},
        {"field": "duration_seconds", "quote": f"{seconds} seconds"},
    ]
    request = {"command": "study.practice.prepare", "language": "en", "messages": [message], "evidence": evidence}
    expected = {
        "date": date, "subject": subject, "topic": topic,
        "correct": correct, "incorrect": incorrect, "blank": blank,
        "duration_minutes": minutes, "duration_seconds": seconds,
    }
    expected_evidence = {
        item["field"]: {
            "value": expected[item["field"]], "message_index": 0, "quote": item["quote"],
            "start": message.index(item["quote"]),
            "end": message.index(item["quote"]) + len(item["quote"]),
        }
        for item in evidence
    }
    return request, expected, expected_evidence


def run_trial(count: int, seed: int) -> dict:
    rng = random.Random(seed)
    fixtures = [fixture(index) for index in range(count)]
    rng.shuffle(fixtures)
    encoded = [json.dumps(request, ensure_ascii=False, separators=(",", ":")) for request, _, _ in fixtures]
    started = time.perf_counter()
    for index, (line, (_, expected, expected_evidence)) in enumerate(zip(encoded, fixtures, strict=True)):
        result = run_json_line(line)
        if result.get("status") != "ready" or result.get("fields") != expected:
            raise AssertionError(f"independent CLI oracle mismatch at row {index}")
        if result.get("write_allowed") is not False or result.get("preview_digest") is None:
            raise AssertionError("CLI exposed a write path or omitted the exact-preview digest")
        if result.get("verified_evidence") != expected_evidence:
            raise AssertionError(f"independent quote/value/offset oracle mismatch at row {index}")
    elapsed = time.perf_counter() - started

    negatives = [
        {"command": "study.practice.prepare", "language": "en", "messages": ["I did not get 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]},
        {"command": "study.practice.prepare", "language": "en", "messages": ["Maybe I got about 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]},
        {"command": "practice.delete", "language": "en", "messages": ["delete"], "evidence": []},
    ]
    for negative in negatives:
        result = run_json_line(json.dumps(negative, ensure_ascii=False))
        if result.get("status") == "ready" or result.get("write_allowed") is True:
            raise AssertionError("unsafe negative CLI probe passed")
    return {"records_checked": count, "seconds": elapsed, "rejected_probes": len(negatives), "provider_calls": 0, "writes": 0}


def main(repeats: int = 5, json_output: str | None = None) -> None:
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    runs = []
    for count in (24, 100):
        run_trial(count, SEED)  # warm-up
        results = [run_trial(count, SEED) for _ in range(repeats)]
        durations = sorted(result["seconds"] for result in results)
        runs.append({
            **results[-1], "p50_seconds": round(durations[len(durations) // 2], 6),
            "p95_seconds": round(durations[-1], 6),
            "oracle": "canonical values plus every quote, source index, and character offset compared to independent seeded input fixtures",
        })
    output = {
        "benchmark": "study_agent_cli_prepare", "seed": SEED, "ai_included": False,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "logical_cpus": __import__("os").cpu_count()},
        "runs": runs,
    }
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if json_output:
        Path(json_output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
