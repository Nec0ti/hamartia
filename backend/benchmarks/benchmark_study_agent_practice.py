"""Benchmark the AI-free verified Study Agent practice draft/create boundary."""

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
import uuid
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


def expected_row(fields, saved, expected_id=None):
    answered = fields["correct"] + fields["incorrect"]
    return {
        **fields, "id": expected_id or saved.id, "created_at": saved.created_at,
        "net": fields["correct"] - fields["incorrect"] / 4,
        "accuracy": fields["correct"] / answered if answered else None,
    }


def approval_id_for(digest=None, duplicate_choice=None):
    # Each explicit approval click gets a fresh key; retries reuse the captured key.
    return str(uuid.uuid4())


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
        approval_id=approval_id_for(draft["preview_digest"]),
    )
    return asyncio.run(practice.practice_agent_create(request, storage))


def evidence_fixture(correct):
    messages = [
        f"I completed a practice test on Functions in Mathematics on {DATE}. "
        f"I got {correct} right, 3 wrong, left 1 blank; it took 45 minutes and 0 seconds."
    ]
    fields = {
        "date": DATE, "subject": "Mathematics", "topic": "Functions", "correct": correct,
        "incorrect": 3, "blank": 1, "duration_minutes": 45, "duration_seconds": 0,
    }
    claims = [
        {"field": "subject", "quote": "in Mathematics"},
        {"field": "topic", "quote": "on Functions"},
        {"field": "date", "quote": f"on {DATE}"},
        {"field": "correct", "quote": f"{correct} right"},
        {"field": "incorrect", "quote": "3 wrong"},
        {"field": "blank", "quote": "left 1 blank"},
        {"field": "duration_minutes", "quote": "it took 45 minutes"},
        {"field": "duration_seconds", "quote": "0 seconds"},
    ]
    return messages, fields, claims


def independently_expected_tool_evidence(messages, fields, claims):
    expected = {}
    for claim in claims:
        quote = claim["quote"]
        start = messages[0].index(quote)
        expected[claim["field"]] = {
            "value": fields[claim["field"]], "message_index": 0, "quote": quote,
            "start": start, "end": start + len(quote),
        }
    return expected


def independently_expected_digest(fields, evidence):
    canonical = json.dumps(
        {"fields": fields, "evidence": evidence},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def create_evidence_entry(messages, language, claims, fields, storage, duplicate_choice=None, approval_id=None):
    draft = asyncio.run(practice.practice_agent_draft(
        practice.AgentDraftRequest(messages=messages, language=language, evidence_claims=claims), storage,
    ))
    if draft["status"] != "ready" or not draft["preview_digest"] or draft["proposal_mismatch"]:
        raise AssertionError("fixed evidence fixture did not produce a verified preview")
    independent_evidence = independently_expected_tool_evidence(messages, fields, claims)
    if draft["fields"] != fields or draft["evidence"] != independent_evidence:
        raise AssertionError("fixed evidence preview differs from the independent transcript oracle")
    expected_digest = independently_expected_digest(fields, independent_evidence)
    if draft["preview_digest"] != expected_digest:
        raise AssertionError("fixed evidence preview digest differs from the independent oracle")
    approval_id = approval_id or approval_id_for()
    request = practice.AgentCreateRequest(
        messages=messages, language=language, evidence_claims=draft["evidence_claims"],
        proposal=draft["proposal"], fields=PracticeSessionCreate.model_validate(draft["fields"]).model_dump(),
        evidence=draft["evidence"], preview_digest=draft["preview_digest"],
        approval_id=approval_id,
        duplicate_choice=duplicate_choice,
    )
    return asyncio.run(practice.practice_agent_create(request, storage)), draft["preview_digest"], approval_id


def run_evidence_tool_protocol():
    """Exercise deterministic host verification/create without provider latency or calls."""
    with tempfile.TemporaryDirectory(prefix="hamartia-agent-evidence-bench-") as directory:
        data_dir = Path(directory)
        storage = StorageService(data_dir)
        with patch.object(practice, "DATA_DIR", data_dir):
            messages_a, fields_a, claims_a = evidence_fixture(12)
            rejected = asyncio.run(practice.practice_agent_draft(
                practice.AgentDraftRequest(
                    messages=messages_a, language="en",
                    evidence_claims=[*claims_a, {"field": "topic", "quote": "topic: invented"}],
                ), storage,
            ))
            if not rejected["proposal_mismatch"] or rejected["fields"].get("topic") != fields_a["topic"]:
                raise AssertionError("unverified evidence hint altered the server-verified preview")
            if rejected["evidence"]["topic"]["quote"] != "on Functions":
                raise AssertionError("unverified evidence hint replaced the verified topic quote")
            if storage.load_list("practice_sessions.json", PracticeSession):
                raise AssertionError("rejected evidence draft wrote a record")

            saved_a, digest_a, approval_a = create_evidence_entry(messages_a, "en", claims_a, fields_a, storage)
            if not saved_a.id.startswith(f"practice_agent_{uuid.UUID(approval_a).hex}_"):
                raise AssertionError("persisted record is not bound to the explicit approval key")
            expected_a = expected_row(fields_a, saved_a)

            duplicate = asyncio.run(practice.practice_agent_draft(
                practice.AgentDraftRequest(messages=messages_a, language="en", evidence_claims=claims_a), storage,
            ))
            if len(duplicate["conflicts"]) != 1:
                raise AssertionError("duplicate evidence preview was not identified")
            unapproved_key = approval_id_for()
            duplicate_request = practice.AgentCreateRequest(
                messages=messages_a, language="en", evidence_claims=duplicate["evidence_claims"],
                proposal=duplicate["proposal"], fields=PracticeSessionCreate.model_validate(duplicate["fields"]).model_dump(),
                evidence=duplicate["evidence"], preview_digest=duplicate["preview_digest"],
                approval_id=unapproved_key,
            )
            try:
                asyncio.run(practice.practice_agent_create(duplicate_request, storage))
            except HTTPException as error:
                if error.status_code != 409:
                    raise
            else:
                raise AssertionError("duplicate evidence preview saved without explicit approval")
            if len(storage.load_list("practice_sessions.json", PracticeSession)) != 1:
                raise AssertionError("unapproved duplicate evidence request wrote a record")

            messages_b, fields_b, claims_b = evidence_fixture(13)
            saved_b, digest_b, approval_b = create_evidence_entry(messages_b, "en", claims_b, fields_b, storage, "new")
            if not saved_b.id.startswith(f"practice_agent_{uuid.UUID(approval_b).hex}_"):
                raise AssertionError("explicit duplicate approval key was not bound to the persisted record")
            expected_b = expected_row(fields_b, saved_b)
            replay_request = practice.AgentCreateRequest(
                messages=messages_b, language="en", evidence_claims=claims_b,
                proposal=fields_b, fields=PracticeSessionCreate.model_validate(fields_b).model_dump(),
                evidence=independently_expected_tool_evidence(messages_b, fields_b, claims_b),
                preview_digest=digest_b, duplicate_choice="new", approval_id=approval_b,
            )
            try:
                replayed = asyncio.run(practice.practice_agent_create(replay_request, storage))
            except HTTPException as error:
                raise AssertionError(f"same-key same-payload approval replay failed: {error.status_code}") from error
            else:
                if replayed.id != saved_b.id:
                    raise AssertionError("replayed explicit approval did not return the existing record")

            messages_c, fields_c, claims_c = evidence_fixture(14)
            draft_c = asyncio.run(practice.practice_agent_draft(
                practice.AgentDraftRequest(messages=messages_c, language="en", evidence_claims=claims_c), storage,
            ))
            changed_same_key = practice.AgentCreateRequest(
                messages=messages_c, language="en", evidence_claims=draft_c["evidence_claims"],
                proposal=draft_c["proposal"], fields=PracticeSessionCreate.model_validate(draft_c["fields"]).model_dump(),
                evidence=draft_c["evidence"], preview_digest=draft_c["preview_digest"],
                duplicate_choice="new", approval_id=approval_b,
            )
            try:
                asyncio.run(practice.practice_agent_create(changed_same_key, storage))
            except HTTPException as error:
                if error.status_code != 409:
                    raise
            else:
                raise AssertionError("same approval key accepted a changed preview")
            if len(storage.load_list("practice_sessions.json", PracticeSession)) != 2:
                raise AssertionError("same-key changed preview wrote a record")

            changed_choice = practice.AgentCreateRequest(
                messages=messages_b, language="en", evidence_claims=claims_b,
                proposal=fields_b, fields=PracticeSessionCreate.model_validate(fields_b).model_dump(),
                evidence=independently_expected_tool_evidence(messages_b, fields_b, claims_b),
                preview_digest=digest_b, approval_id=approval_b,
            )
            try:
                asyncio.run(practice.practice_agent_create(changed_choice, storage))
            except HTTPException as error:
                if error.status_code != 409:
                    raise
            else:
                raise AssertionError("same approval key accepted a changed duplicate choice")
            if len(storage.load_list("practice_sessions.json", PracticeSession)) != 2:
                raise AssertionError("same-key changed duplicate choice wrote a record")

            intentional_approval = str(uuid.uuid4())
            saved_c, digest_c, returned_approval = create_evidence_entry(
                messages_b, "en", claims_b, fields_b, storage, "new", approval_id=intentional_approval,
            )
            if returned_approval != intentional_approval or saved_c.id == saved_b.id:
                raise AssertionError("separate intentional duplicate approval did not receive its own replay key")
            if not saved_c.id.startswith(f"practice_agent_{uuid.UUID(intentional_approval).hex}_"):
                raise AssertionError("intentional duplicate was not bound to its approval key")
            expected_c = expected_row(fields_b, saved_c)

            persisted = storage.load_list("practice_sessions.json", PracticeSession)
            actual = [item.model_dump() for item in persisted]
            assert_oracle(actual, [expected_a, expected_b, expected_c], "provider-free evidence tool full persisted rows")
            return {
                "records_checked": 3,
                "verified_previews": 4,
                "fixed_evidence_claims": len(claims_a),
                "rejected_evidence_writes": 0,
                "unapproved_duplicate_writes": 0,
                "replayed_approval_writes": 0,
                "same_key_changed_preview_writes": 0,
                "same_key_changed_choice_writes": 0,
                "intentional_identical_duplicate_saves": 1,
                "provider_calls": 0,
                "inference_or_latency_included": False,
                "oracle": "independent fixture values, exact quote offsets and digest, captured approval UUID binding, and every persisted row",
            }


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
                approval_id=str(uuid.uuid4()),
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
        "evidence_tool_protocol": run_evidence_tool_protocol(),
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
