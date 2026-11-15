"""Benchmark the AI-free verified Study Agent practice draft/create boundary."""

import argparse
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api import practice
from app.models.schemas import PracticeSession, PracticeSessionCreate
from app.services.storage import StorageService
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

SEED = 20261115
DATE = "2026-11-15"


def entry(index: int):
    fields = {
        "date": DATE, "subject": f"Benchmark subject {index:04d}", "topic": f"Topic {index % 17:02d}",
        "correct": index % 21, "incorrect": (index * 7) % 8, "blank": (index * 3) % 6,
        "duration_minutes": 5 + index % 80, "duration_seconds": index % 60,
    }
    if not fields["correct"] + fields["incorrect"] + fields["blank"]:
        fields["blank"] = 1
    return [", ".join(f"{field}: {value}" for field, value in fields.items())], fields


def expected_row(fields, saved):
    answered = fields["correct"] + fields["incorrect"]
    return {
        **fields, "id": saved.id, "created_at": saved.created_at,
        "net": fields["correct"] - fields["incorrect"] / 4,
        "accuracy": fields["correct"] / answered if answered else None,
    }


def create_entry(messages, fields, storage):
    draft = asyncio.run(practice.practice_agent_draft(
        practice.AgentDraftRequest(messages=messages, language="en", proposal=fields), storage,
    ))
    if draft["missing"] or draft["ambiguous"] or not draft["preview_digest"] or draft["proposal_mismatch"]:
        raise AssertionError("benchmark fixture unexpectedly needed clarification")
    request = practice.AgentCreateRequest(
        messages=messages, language="en", proposal=draft["proposal"],
        fields=PracticeSessionCreate.model_validate(draft["fields"]).model_dump(),
        evidence=draft["evidence"], preview_digest=draft["preview_digest"],
    )
    return asyncio.run(practice.practice_agent_create(request, storage))


def run_trial(count):
    with tempfile.TemporaryDirectory(prefix="hamartia-agent-entry-bench-") as directory:
        data_dir = Path(directory)
        storage = StorageService(data_dir)
        with patch.object(practice, "DATA_DIR", data_dir):
            started = time.perf_counter()
            expected = []
            for index in range(count):
                messages, fields = entry(index)
                expected.append(expected_row(fields, create_entry(messages, fields, storage)))
            elapsed = time.perf_counter() - started

            persisted = storage.load_list("practice_sessions.json", PracticeSession)
            actual = [item.model_dump() for item in persisted]
            assert_oracle(actual, expected, "practice-entry full persisted rows")
            oracle_probe = probe_oracle_self_check(
                actual, expected,
                lambda rows: rows[0].__setitem__("correct", rows[0]["correct"] + 1),
                "practice entry changed count",
            )

            # A provider can overguess an allowed field, but server extraction wins and does not write.
            messages, fields = entry(0)
            before = len(persisted)
            mismatched = asyncio.run(practice.practice_agent_draft(
                practice.AgentDraftRequest(messages=messages, language="en", proposal={**fields, "correct": fields["correct"] + 1}), storage,
            ))
            if not mismatched["proposal_mismatch"] or mismatched["fields"]["correct"] != fields["correct"]:
                raise AssertionError("invented proposal value was not replaced by student evidence")
            if len(storage.load_list("practice_sessions.json", PracticeSession)) != before:
                raise AssertionError("mismatched proposal wrote a record")

            draft = asyncio.run(practice.practice_agent_draft(
                practice.AgentDraftRequest(messages=messages, language="en", proposal=fields), storage,
            ))
            if len(draft["conflicts"]) != 1:
                raise AssertionError("duplicate record was not identified")
            request = practice.AgentCreateRequest(
                messages=messages, language="en", proposal=draft["proposal"],
                fields=PracticeSessionCreate.model_validate(draft["fields"]).model_dump(),
                evidence=draft["evidence"], preview_digest=draft["preview_digest"],
            )
            try:
                asyncio.run(practice.practice_agent_create(request, storage))
            except HTTPException as error:
                if error.status_code != 409:
                    raise
            else:
                raise AssertionError("duplicate record saved without explicit approval")
            if len(storage.load_list("practice_sessions.json", PracticeSession)) != before:
                raise AssertionError("unapproved duplicate wrote a record")

            return {
                "seconds": elapsed,
                "records": count,
                "persisted_bytes": (data_dir / "practice_sessions.json").stat().st_size,
                "oracle_self_checks": [oracle_probe],
                "mismatched_proposal_writes": 0,
                "unapproved_duplicate_writes": 0,
            }


def measure_workload(count, repeats):
    run_trial(count)  # warm-up; correctness probes are outside every timed interval
    runs = [run_trial(count) for _ in range(repeats)]
    durations = sorted(item["seconds"] for item in runs)
    result = runs[-1]
    result.update({
        "full_draft_and_approved_create_p50_seconds": round(durations[len(durations) // 2], 6),
        "full_draft_and_approved_create_p95_seconds": round(durations[-1], 6),
        "correctness": "every persisted field, computed value, and metadata field matches the independent input oracle",
        "provider_calls": 0,
    })
    return result


def main(repeats=5, json_output=None):
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    emit({
        "benchmark": "study_agent_practice_entry",
        "seed": SEED,
        "runs": [measure_workload(count, repeats) for count in (24, 100)],
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
