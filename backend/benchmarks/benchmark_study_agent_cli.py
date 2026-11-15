"""AI-free benchmark for the strict, quote-grounded Study Agent CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import time
from pathlib import Path

from app.hamartia_cli import run_json_line

SEED = 20261115

def fixture(index: int) -> tuple[dict, dict, dict, str]:
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
    if index % 3 == 0:
        message = (
            f"I completed a practice test on {topic} in {subject} on {date}. "
            f"I got {correct} right, {incorrect} wrong, left {blank} blank; "
            f"it took {minutes} minutes and {seconds} seconds."
        )
        language = "en"
        evidence = [
            {"field": "subject", "quote": f"in {subject}"}, {"field": "topic", "quote": f"on {topic}"},
            {"field": "date", "quote": f"on {date}"}, {"field": "correct", "quote": f"{correct} right"},
            {"field": "incorrect", "quote": f"{incorrect} wrong"}, {"field": "blank", "quote": f"left {blank} blank"},
            {"field": "duration_minutes", "quote": f"{minutes} minutes"}, {"field": "duration_seconds", "quote": f"{seconds} seconds"},
        ]
    elif index % 3 == 1:
        message = (
            f"date: {date}; topic: {topic}; subject: {subject}; correct: {correct}; wrong: {incorrect}; "
            f"blank: {blank}; duration_minutes: {minutes}; duration_seconds: {seconds}"
        )
        language = "en"
        evidence = [
            {"field": "date", "quote": f"date: {date}"}, {"field": "topic", "quote": f"topic: {topic}"},
            {"field": "subject", "quote": f"subject: {subject}"}, {"field": "correct", "quote": f"correct: {correct}"},
            {"field": "incorrect", "quote": f"wrong: {incorrect}"}, {"field": "blank", "quote": f"blank: {blank}"},
            {"field": "duration_minutes", "quote": f"duration_minutes: {minutes}"},
            {"field": "duration_seconds", "quote": f"duration_seconds: {seconds}"},
        ]
    else:
        message = (
            f"tarih: {date}; ders: {subject}; konu: {topic}; doğru: {correct}; yanlış: {incorrect}; "
            f"boş: {blank}; duration_minutes: {minutes}; duration_seconds: {seconds}"
        )
        language = "tr"
        evidence = [
            {"field": "date", "quote": f"tarih: {date}"}, {"field": "subject", "quote": f"ders: {subject}"},
            {"field": "topic", "quote": f"konu: {topic}"}, {"field": "correct", "quote": f"doğru: {correct}"},
            {"field": "incorrect", "quote": f"yanlış: {incorrect}"}, {"field": "blank", "quote": f"boş: {blank}"},
            {"field": "duration_minutes", "quote": f"duration_minutes: {minutes}"},
            {"field": "duration_seconds", "quote": f"duration_seconds: {seconds}"},
        ]
    request = {"command": "study.practice.prepare", "language": language, "messages": [message], "evidence": evidence}
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
    canonical = json.dumps({"fields": expected, "evidence": expected_evidence}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return request, expected, expected_evidence, expected_digest


def _assert_rejected_probe(request: dict, *, status: str, field: str | None = None, missing: bool = False) -> dict:
    result = run_json_line(json.dumps(request, ensure_ascii=False))
    if result.get("status") != status or result.get("write_allowed") is True:
        raise AssertionError(f"expected read-only {status} result, got {result.get('status')}")
    if field:
        if missing and (field not in result.get("missing", []) or field in result.get("ambiguous", {})):
            raise AssertionError(f"{field} did not remain specifically missing")
        if not missing and (field not in result.get("ambiguous", {}) or field in result.get("missing", [])):
            raise AssertionError(f"{field} did not remain specifically ambiguous")
    return result


def adversarial_probes(seed: int) -> int:
    base, expected, _evidence, _digest = fixture(seed)
    positives = base["evidence"]
    probes = [
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 or 7 right."], "evidence": [{"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got five or 7 right."], "evidence": [{"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["correct: 5, or 7"], "evidence": [{"field": "correct", "quote": "correct: 5, or 7"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "I got 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}, {"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "I got 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["correct: 5 or 7"], "evidence": [{"field": "correct", "quote": "correct: 5 or 7"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or November 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 11/16/2026."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 16.11.2026."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or Nov 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 15 Kasım."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or sixty seconds."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or half an hour."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["45 dakika ya da bir buçuk saat sürdü."], "evidence": [{"field": "duration_minutes", "quote": "45 dakika"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I practiced Functions."], "evidence": [{"field": "topic", "quote": "practiced Functions"}]}, "incomplete", "correct", True),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I practiced Functions."], "evidence": [{"field": "topic", "quote": "unquoted guess"}]}, "incomplete", "correct", True),
    ]
    for request, status, field, is_missing in probes:
        _assert_rejected_probe(request, status=status, field=field, missing=is_missing)

    # A correction is the one allowed resolution of conflicting user turns.
    correction = {**base, "messages": [*base["messages"], "Correction: I got 3 right."]}
    correction["evidence"] = [item for item in positives if item["field"] != "correct"] + [
        {"field": "correct", "quote": positives[[item["field"] for item in positives].index("correct")]["quote"]},
        {"field": "correct", "quote": "Correction: I got 3 right"},
    ]
    corrected = run_json_line(json.dumps(correction, ensure_ascii=False))
    expected_corrected = {**expected, "correct": 3}
    expected_evidence = {
        item["field"]: {
            "value": expected_corrected[item["field"]],
            "message_index": 1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0,
            "quote": item["quote"],
            "start": correction["messages"][1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0].index(item["quote"]),
            "end": correction["messages"][1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0].index(item["quote"]) + len(item["quote"]),
        }
        for item in correction["evidence"] if not (item["field"] == "correct" and not item["quote"].startswith("Correction"))
    }
    corrected_digest = hashlib.sha256(json.dumps({"fields": expected_corrected, "evidence": expected_evidence}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if corrected.get("status") != "ready" or corrected.get("fields") != expected_corrected or corrected.get("verified_evidence") != expected_evidence or corrected.get("preview_digest") != corrected_digest:
        raise AssertionError("explicit correction did not resolve the transcript to the independent corrected oracle")
    return len(probes) + 1


def run_trial(count: int, seed: int) -> dict:
    rng = random.Random(seed)
    fixtures = [fixture(index) for index in range(count)]
    rng.shuffle(fixtures)
    encoded = [json.dumps(request, ensure_ascii=False, separators=(",", ":")) for request, _, _, _ in fixtures]
    started = time.perf_counter()
    for index, (line, (_, expected, expected_evidence, expected_digest)) in enumerate(zip(encoded, fixtures, strict=True)):
        result = run_json_line(line)
        if result.get("status") != "ready" or result.get("fields") != expected:
            raise AssertionError(f"independent CLI oracle mismatch at row {index}")
        if result.get("write_allowed") is not False or result.get("preview_digest") != expected_digest:
            raise AssertionError(f"independent exact-preview digest mismatch at row {index}")
        if result.get("verified_evidence") != expected_evidence:
            raise AssertionError(f"independent quote/value/offset oracle mismatch at row {index}")
    elapsed = time.perf_counter() - started

    negatives = [
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I did not get 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["Maybe I got about 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "practice.delete", "language": "en", "messages": ["delete"], "evidence": []}, "error", None, False),
    ]
    for request, status, field, missing in negatives:
        _assert_rejected_probe(request, status=status, field=field, missing=missing)
    adversarial_count = adversarial_probes(seed)
    return {"records_checked": count, "seconds": elapsed, "rejected_probes": len(negatives) + adversarial_count, "provider_calls": 0, "writes": 0}


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
            "oracle": "diversified EN/TR and labeled/natural fixtures; independent canonical values, every quote/source index/offset, and independently reconstructed preview digests; adversarial exact-status and explicit-correction controls",
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
