"""Benchmark deterministic host learning-evidence preview/create and signed state flow."""

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api import learning_evidence
from app.models.schemas import LearningEvidence
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_learning_evidence import (
    issue_learning_evidence_state_token,
    prepare_learning_evidence,
    resolve_learning_evidence_state_token,
)
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

SEED = 20261116


def fixture(index: int):
    activity = f"I completed solving {index + 2} equations."
    subject = f"Synthetic subject {index % 9:02d}"
    topic = f"Synthetic topic {index % 17:02d}"
    date = f"2026-11-{index % 28 + 1:02d}"
    observation = f"Comparing the two solution methods helped me notice pattern {index:04d}."
    messages = [activity, subject, topic, date, observation]
    claims = [
        {"field": field, "quote": quote}
        for field, quote in zip(("activity", "subject", "topic", "date", "observation"), messages)
    ]
    if index % 2 == 0:
        url = f"https://example.org/reference/{index:04d}"
        messages[-1] += f" {url}"
        claims.append({"field": "reference_url", "quote": url})
    expected_fields = {
        "activity": activity, "subject": subject, "topic": topic, "date": date,
        "observation": observation,
        "reference_url": f"https://example.org/reference/{index:04d}" if index % 2 == 0 else "",
    }
    return messages, claims, expected_fields


def expected_evidence(messages, claims, expected_fields):
    expected = {}
    for claim in claims:
        quote = claim["quote"]
        matches = []
        for message_index, message in enumerate(messages):
            position = message.find(quote)
            while position >= 0:
                matches.append((message_index, position))
                position = message.find(quote, position + 1)
        if len(matches) != 1:
            raise AssertionError("benchmark fixture quote is absent or repeated")
        message_index, start = matches[0]
        expected[claim["field"]] = {
            "value": expected_fields[claim["field"]],
            "message_index": message_index,
            "quote": quote,
            "start": start,
            "end": start + len(quote),
        }
    return expected


def approval_fingerprint(body):
    approved = {key: value for key, value in body.items() if key != "approval_id"}
    canonical = json.dumps(approved, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def provider_tripwires():
    stack = ExitStack()
    for name in ("study_chat", "study_practice_prepare", "study_learning_evidence_prepare"):
        stack.enter_context(patch.object(AIService, name, side_effect=AssertionError(f"provider call during host-only benchmark: {name}")))
    return stack


def preview_and_create(index, storage):
    messages, claims, expected_fields = fixture(index)
    draft = asyncio.run(learning_evidence.learning_evidence_agent_draft(
        learning_evidence.AgentLearningEvidenceDraftRequest(
            messages=messages, language="en", evidence_claims=claims,
        ),
    ))
    expected = expected_evidence(messages, claims, expected_fields)
    if draft["status"] != "ready" or draft["fields"] != expected_fields or draft["verified_evidence"] != expected:
        raise AssertionError("host evidence preview differs from independent literal fixture oracle")
    canonical = json.dumps({
        "messages": messages, "language": "en", "fields": expected_fields, "evidence": expected,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if draft["preview_digest"] != hashlib.sha256(canonical).hexdigest():
        raise AssertionError("preview digest differs from independent canonical snapshot oracle")
    approval_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"learning-evidence:{index}"))
    body = {
        "messages": messages, "language": "en", "evidence_claims": claims,
        "fields": expected_fields, "evidence": expected,
        "preview_digest": draft["preview_digest"], "approval_id": approval_id,
    }
    request = learning_evidence.AgentLearningEvidenceCreateRequest.model_validate(body)
    created_at_start = datetime.now(timezone.utc)
    record = asyncio.run(learning_evidence.learning_evidence_agent_create(request, storage))
    created_at_end = datetime.now(timezone.utc)
    expected_id = f"learning_evidence_agent_{uuid.UUID(approval_id).hex}_{approval_fingerprint(body)}"
    if record.id != expected_id:
        raise AssertionError("stored ID differs from independently recomputed approval fingerprint")
    created_at = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
    if created_at.tzinfo != timezone.utc or not created_at_start.replace(microsecond=0) <= created_at <= created_at_end.replace(microsecond=0):
        raise AssertionError("stored timestamp is outside the measured UTC create window")
    expected_record = {**expected_fields, "id": expected_id, "created_at": record.created_at}
    return record, expected_record, body


def signed_state_transition(index):
    prefix = [f"I completed reading chapter {index + 1}.", "Synthetic biology"]
    prior_claims = [
        {"field": "activity", "quote": prefix[0]},
        {"field": "subject", "quote": prefix[1]},
    ]
    prior = prepare_learning_evidence(prefix, "en", prior_claims)
    if prior["expected_field"] != "topic" or prior["rejected_claims"]:
        raise AssertionError("host prior state did not select the next expected field")
    token = issue_learning_evidence_state_token(prefix, "en", prior["verified_evidence"])
    messages = [*prefix, f"Synthetic topic {index + 1}"]
    resolved = resolve_learning_evidence_state_token(token, messages, "en")
    if resolved != prior_claims:
        raise AssertionError("signed state did not recover exactly the host-verified prior claims")
    prepared = prepare_learning_evidence(messages, "en", [*resolved, {
        "field": "topic", "quote": messages[-1],
    }])
    if prepared["expected_field"] != "date" or prepared["rejected_claims"]:
        raise AssertionError("appended current turn did not advance exactly one expected field")
    try:
        resolve_learning_evidence_state_token(token, messages, "en")
    except ValueError:
        pass
    else:
        raise AssertionError("signed state token replay was accepted")


def run_trial(count):
    with tempfile.TemporaryDirectory(prefix="hamartia-learning-evidence-bench-") as directory, provider_tripwires():
        storage = StorageService(Path(directory))
        state_started = time.perf_counter()
        state_transitions = 100
        for index in range(state_transitions):
            signed_state_transition(index)
        state_elapsed = time.perf_counter() - state_started
        seen_ids = set()
        expected_rows = []
        started = time.perf_counter()
        replay_body = None
        for index in range(count):
            record, expected, body = preview_and_create(index, storage)
            if record.id in seen_ids:
                raise AssertionError("approval-generated record IDs are not unique")
            seen_ids.add(record.id)
            expected_rows.append(expected)
            if index == 0:
                replay_body = body
        elapsed = time.perf_counter() - started

        # Same-body retries are idempotent; changed body/preview under the same approval is a conflict.
        replay = asyncio.run(learning_evidence.learning_evidence_agent_create(
            learning_evidence.AgentLearningEvidenceCreateRequest.model_validate(replay_body), storage,
        ))
        if replay.id != expected_rows[0]["id"]:
            raise AssertionError("same-body retry did not return the original row")
        changed = json.loads(json.dumps(replay_body))
        changed["fields"]["observation"] += " changed"
        try:
            asyncio.run(learning_evidence.learning_evidence_agent_create(
                learning_evidence.AgentLearningEvidenceCreateRequest.model_validate(changed), storage,
            ))
        except HTTPException as error:
            if error.status_code != 409:
                raise AssertionError("altered replay did not return 409") from error
        else:
            raise AssertionError("altered replay unexpectedly created another row")

        concurrent_messages, concurrent_claims, concurrent_fields = fixture(1000)
        concurrent_draft = asyncio.run(learning_evidence.learning_evidence_agent_draft(
            learning_evidence.AgentLearningEvidenceDraftRequest(
                messages=concurrent_messages, language="en", evidence_claims=concurrent_claims,
            ),
        ))
        concurrent_evidence = expected_evidence(concurrent_messages, concurrent_claims, concurrent_fields)
        concurrent_approval = str(uuid.uuid5(uuid.NAMESPACE_URL, "learning-evidence:concurrent"))
        concurrent_body = {
            "messages": concurrent_messages, "language": "en", "evidence_claims": concurrent_claims,
            "fields": concurrent_fields, "evidence": concurrent_evidence,
            "preview_digest": concurrent_draft["preview_digest"], "approval_id": concurrent_approval,
        }
        concurrent_request = learning_evidence.AgentLearningEvidenceCreateRequest.model_validate(concurrent_body)
        concurrent_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            concurrent_records = list(pool.map(
                lambda _: asyncio.run(learning_evidence.learning_evidence_agent_create(concurrent_request, storage)),
                range(8),
            ))
        concurrent_seconds = time.perf_counter() - concurrent_start
        concurrent_ids = {record.id for record in concurrent_records}
        if len(concurrent_ids) != 1:
            raise AssertionError("concurrent same-approval retries created different IDs")
        concurrent_record = concurrent_records[0]
        concurrent_expected_id = f"learning_evidence_agent_{uuid.UUID(concurrent_approval).hex}_{approval_fingerprint(concurrent_body)}"
        if concurrent_record.id != concurrent_expected_id:
            raise AssertionError("concurrent approval ID differs from independent fingerprint")
        expected_rows.append({**concurrent_fields, "id": concurrent_expected_id, "created_at": concurrent_record.created_at})

        persisted = storage.load_list("learning_evidence.json", LearningEvidence)
        actual_rows = [item.model_dump() for item in persisted]
        assert_oracle(actual_rows, expected_rows, "learning-evidence full persisted records")
        if len(actual_rows) != count + 1:
            raise AssertionError("exact replay or altered replay changed persisted row count")
        oracle_probe = probe_oracle_self_check(
            actual_rows, expected_rows,
            lambda rows: rows[0].__setitem__("observation", "wrong"),
            "learning-evidence observation corrupted",
        )

        # Invalid and incomplete evidence cannot produce a write, even through create.
        invalid_messages = ["I might complete these exercises tomorrow.", "Biology", "Cell division", "2026-11-16", "A synthetic observation."]
        invalid_claims = [
            {"field": field, "quote": quote}
            for field, quote in zip(("activity", "subject", "topic", "date", "observation"), invalid_messages)
        ]
        invalid = prepare_learning_evidence(invalid_messages, "en", invalid_claims)
        if invalid["status"] != "ambiguous" or invalid["preview_digest"] is not None:
            raise AssertionError("hypothetical completion produced an approvable preview")
        invalid_body = {
            "messages": invalid_messages, "language": "en", "evidence_claims": invalid_claims,
            "fields": {"date": "2026-11-16", "subject": "Biology", "topic": "Cell division", "activity": invalid_messages[0], "observation": invalid_messages[4], "reference_url": ""},
            "evidence": {}, "preview_digest": "0" * 64, "approval_id": str(uuid.uuid4()),
        }
        try:
            asyncio.run(learning_evidence.learning_evidence_agent_create(
                learning_evidence.AgentLearningEvidenceCreateRequest.model_validate(invalid_body), storage,
            ))
        except HTTPException as error:
            if error.status_code != 422:
                raise AssertionError("invalid evidence create did not fail closed") from error
        else:
            raise AssertionError("invalid evidence unexpectedly wrote a record")
        if len(storage.load_list("learning_evidence.json", LearningEvidence)) != count + 1:
            raise AssertionError("invalid evidence changed persisted collection")

        return {
            "records": count,
            "signed_state_transitions": state_transitions,
            "signed_state_transition_seconds": round(state_elapsed, 6),
            "signed_state_transitions_per_second": round(state_transitions / state_elapsed, 2) if state_elapsed else None,
            "seconds": round(elapsed, 6),
            "records_per_second": round(count / elapsed, 2) if elapsed else None,
            "persisted_bytes": (Path(directory) / "learning_evidence.json").stat().st_size,
            "same_body_replays": 1,
            "altered_body_conflicts": 1,
            "concurrent_same_approval_requests": len(concurrent_records),
            "concurrent_same_approval_rows": 1,
            "concurrent_same_approval_seconds": round(concurrent_seconds, 6),
            "invalid_or_hypothetical_writes": 0,
            "provider_tripwire_calls": 0,
            "oracle_self_checks": [oracle_probe],
            "correctness": "full rows, exact quote offsets, URL policy, preview digest, approval fingerprint, signed-prefix transitions, one-use replay rejection, and no-write cases match independent oracles",
        }


def main(repeats=5, json_output=None):
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    run_trial(2)  # correctness warm-up outside timed runs
    runs = []
    for count in (24, 64):
        trials = [run_trial(count) for _ in range(repeats)]
        durations = sorted(item["seconds"] for item in trials)
        result = dict(trials[-1])
        result["full_preview_and_approved_create_p50_seconds"] = round(durations[len(durations) // 2], 6)
        result["full_preview_and_approved_create_p95_seconds"] = round(durations[-1], 6)
        state_durations = sorted(item["signed_state_transition_seconds"] for item in trials)
        result["signed_state_transition_p50_seconds"] = round(state_durations[len(state_durations) // 2], 6)
        result["signed_state_transition_p95_seconds"] = round(state_durations[-1], 6)
        result["warmup_trials_excluded"] = 1
        runs.append(result)
    emit({
        "benchmark": "study_agent_learning_evidence_host_flow",
        "seed": SEED,
        "provider_execution": "excluded; AIService provider entry points are fail-fast patched",
        "runs": runs,
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
