"""Benchmark deterministic host-only single-subject branch-exam capture."""

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api import exams
from app.models.schemas import Exam, ExamScoringProfile, legacy_yks_profile
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_exam import (
    EXAM_FIELDS,
    ExamQuote,
    issue_exam_state_token,
    prepare_exam_capture,
    resolve_exam_state_token,
)
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

SEED = 20261116


def fixture(index: int):
    values = [
        f"2026-11-{index % 28 + 1:02d}",
        f"Synthetic Biology {index:04d}",
        str(20 + index % 40),
        str(index % 9),
        str(index % 5),
        str(30 + index % 90),
        str(index % 60),
    ]
    messages = list(values)
    claims = [{"field": field, "quote": value} for field, value in zip(EXAM_FIELDS, values, strict=True)]
    fields = {
        "date": values[0], "exam_type": "branch", "subject": values[1],
        "correct": int(values[2]), "incorrect": int(values[3]), "blank": int(values[4]),
        "duration_minutes": int(values[5]), "duration_seconds": int(values[6]),
        "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1, "sections": [],
    }
    return messages, claims, fields


def expected_derived(fields):
    # Independent literal implementation of the existing legacy net and XP rules.
    net = fields["correct"] - fields["incorrect"] / 4
    duration = fields["duration_minutes"] or 1
    xp = max(0, int((net * fields["correct"] * 1.5) - (duration * fields["incorrect"] * 0.25)))
    return {"net": net, "xp": xp}


def canonical_digest(fields, evidence, profile, derived):
    canonical = json.dumps({
        "fields": fields,
        "evidence": evidence,
        "scoring_profile_snapshot": profile.model_dump(),
        "derived": derived,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def request_for(messages, field, quote, token, profile):
    return exams.AgentExamDraftRequest(
        messages=messages, language="en", expected_exam_field=field,
        state_token=token, scoring_profile_id=profile.profile_id,
        scoring_profile_version=profile.version,
        evidence_claims=[] if quote is None else [ExamQuote(field=field, quote=quote)],
    )


def preview(messages, claims, storage, profile):
    token = None
    result = None
    current_messages = []
    for field, claim in zip(EXAM_FIELDS, claims, strict=True):
        current_messages.append(claim["quote"])
        result = asyncio.run(exams.exam_agent_draft(
            request_for(current_messages, field, claim["quote"], token, profile), storage,
        ))
        token = result["state_token"]
    return result


def approval_body(index, messages, draft, profile):
    return {
        "messages": messages,
        "language": "en",
        "expected_exam_field": EXAM_FIELDS[-1],
        "state_token": None,
        "scoring_profile_id": profile.profile_id,
        "scoring_profile_version": profile.version,
        "evidence_claims": draft["evidence_claims"],
        "fields": draft["fields"],
        "evidence": draft["verified_evidence"],
        "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
        "derived": draft["derived"],
        "preview_digest": draft["preview_digest"],
        "approval_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"branch-exam:{index}")),
    }


def approval_id_fingerprint(body):
    fingerprint_body = {
        key: body[key] for key in (
            "messages", "language", "expected_exam_field", "evidence_claims", "fields",
            "evidence", "scoring_profile_snapshot", "derived", "preview_digest",
        )
    }
    canonical = json.dumps(fingerprint_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def signed_state_transition(index, profile):
    messages = [f"2026-11-{index % 28 + 1:02d}"]
    claims = [{"field": "date", "quote": messages[0], "message_index": 0}]
    token = issue_exam_state_token(messages, "en", claims, profile.profile_id, profile.version)
    extended = [*messages, f"Synthetic Biology {index:04d}"]
    resolved = resolve_exam_state_token(token, extended, "en", profile.profile_id, profile.version)
    if resolved != claims:
        raise AssertionError("signed host state did not preserve the exact date quote")
    expected = prepare_exam_capture(extended, "en", resolved, [{"field": "subject", "quote": extended[-1]}], profile)
    if expected["expected_field"] != "correct" or expected["status"] != "incomplete":
        raise AssertionError("host transcript did not advance to the correct-count follow-up")
    try:
        resolve_exam_state_token(token, extended, "en", profile.profile_id, profile.version)
    except ValueError:
        pass
    else:
        raise AssertionError("signed state token replay was accepted")


def provider_tripwires():
    stack = ExitStack()
    names = (
        "analyze_question", "study_chat", "study_practice_prepare",
        "study_learning_evidence_prepare", "study_question_prepare", "study_exam_prepare",
    )
    for name in names:
        stack.enter_context(patch.object(
            AIService, name,
            side_effect=AssertionError(f"provider call during host-only benchmark: {name}"),
        ))
    return stack


def run_trial(count):
    with tempfile.TemporaryDirectory(prefix="hamartia-exam-capture-bench-") as directory, provider_tripwires():
        storage = StorageService(Path(directory))
        profile = legacy_yks_profile()
        state_count = 100
        started_state = time.perf_counter()
        for index in range(state_count):
            signed_state_transition(index, profile)
        state_seconds = time.perf_counter() - started_state

        expected_rows = []
        ids = set()
        replay_body = None
        started = time.perf_counter()
        for index in range(count):
            messages, claims, expected_fields = fixture(index)
            draft = preview(messages, claims, storage, profile)
            expected_evidence = {
                claim["field"]: {"quote": claim["quote"], "message_index": position}
                for position, claim in enumerate(claims)
            }
            derived = expected_derived(expected_fields)
            if (draft["status"] != "ready" or draft["fields"] != expected_fields
                    or draft["verified_evidence"] != expected_evidence or draft["derived"] != derived):
                raise AssertionError("host branch-exam preview differs from independent literal fixture oracle")
            if draft["preview_digest"] != canonical_digest(expected_fields, expected_evidence, profile, derived):
                raise AssertionError("preview digest differs from independent canonical snapshot oracle")
            body = approval_body(index, messages, draft, profile)
            request = exams.AgentExamCreateRequest.model_validate(body)
            record = asyncio.run(exams.exam_agent_create(request, storage))
            expected_id = f"exam_agent_{uuid.UUID(body['approval_id']).hex}_{approval_id_fingerprint(body)}"
            if record.id != expected_id or record.id in ids:
                raise AssertionError("approval ID differs from the independent fingerprint or is duplicated")
            ids.add(record.id)
            expected_record = {
                "id": expected_id,
                **{key: value for key, value in expected_fields.items() if key not in {"scoring_profile_id", "scoring_profile_version"}},
                "created_at": record.created_at,
                "scoring_profile": profile.model_dump(),
                "total": expected_fields["correct"] + expected_fields["incorrect"],
                "net": derived["net"],
                "xp": derived["xp"],
            }
            if record.model_dump() != expected_record:
                raise AssertionError("created record differs from independent field, profile, net, or XP oracle")
            expected_rows.append(expected_record)
            if index == 0:
                replay_body = body
        elapsed = time.perf_counter() - started

        replay = asyncio.run(exams.exam_agent_create(
            exams.AgentExamCreateRequest.model_validate(replay_body), storage,
        ))
        if replay.id != expected_rows[0]["id"]:
            raise AssertionError("same-body retry did not return the original exam")
        altered = json.loads(json.dumps(replay_body))
        altered["fields"]["correct"] += 1
        try:
            asyncio.run(exams.exam_agent_create(exams.AgentExamCreateRequest.model_validate(altered), storage))
        except HTTPException as error:
            if error.status_code != 409:
                raise AssertionError("altered approval replay did not return 409") from error
        else:
            raise AssertionError("altered approval replay unexpectedly succeeded")

        messages, claims, fields = fixture(10_000)
        concurrent_draft = preview(messages, claims, storage, profile)
        body = approval_body(10_000, messages, concurrent_draft, profile)
        request = exams.AgentExamCreateRequest.model_validate(body)
        started_concurrent = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(
                lambda _: asyncio.run(exams.exam_agent_create(request, storage)), range(8),
            ))
        concurrent_seconds = time.perf_counter() - started_concurrent
        if len({item.id for item in records}) != 1:
            raise AssertionError("concurrent same-approval requests did not converge on one row")
        concurrent_messages, _, concurrent_fields = fixture(10_000)
        concurrent_derived = expected_derived(concurrent_fields)
        concurrent_expected = {
            "id": records[0].id,
            **{key: value for key, value in concurrent_fields.items() if key not in {"scoring_profile_id", "scoring_profile_version"}},
            "created_at": records[0].created_at,
            "scoring_profile": profile.model_dump(),
            "total": concurrent_fields["correct"] + concurrent_fields["incorrect"],
            "net": concurrent_derived["net"],
            "xp": concurrent_derived["xp"],
        }
        if records[0].model_dump() != concurrent_expected:
            raise AssertionError("concurrent record differs from independent field, profile, net, or XP oracle")
        expected_rows.append(concurrent_expected)

        # A hypothetical or malformed first value cannot produce a preview or persisted row.
        invalid_messages = ["Maybe next month", *[f"Synthetic answer {i}" for i in range(6)]]
        invalid = prepare_exam_capture(
            invalid_messages, "en", [], [{"field": "date", "quote": invalid_messages[0]}], profile,
        )
        if invalid["status"] != "ambiguous" or invalid["preview_digest"] is not None:
            raise AssertionError("ambiguous date produced an approvable branch-exam preview")

        persisted = storage.load_list("exams.json", Exam)
        actual_rows = [item.model_dump() for item in persisted]
        assert_oracle(actual_rows, expected_rows, "branch-exam full persisted rows")
        if len(actual_rows) != count + 1:
            raise AssertionError("replay, changed approval, or invalid input changed persisted row count")
        oracle_probe = probe_oracle_self_check(
            actual_rows, expected_rows,
            lambda rows: rows[0].__setitem__("subject", "wrong subject"),
            "branch-exam subject corrupted",
        )
        return {
            "records": count,
            "host_preview_and_approved_create_seconds": round(elapsed, 6),
            "records_per_second": round(count / elapsed, 2) if elapsed else None,
            "persisted_bytes": (Path(directory) / "exams.json").stat().st_size,
            "signed_state_transitions": state_count,
            "signed_state_transition_seconds": round(state_seconds, 6),
            "signed_state_transitions_per_second": round(state_count / state_seconds, 2) if state_seconds else None,
            "concurrent_approval_requests": len(records),
            "concurrent_approval_rows": 1,
            "concurrent_approval_seconds": round(concurrent_seconds, 6),
            "same_body_replays": 1,
            "altered_replay_conflicts": 1,
            "invalid_preview_or_write_count": 0,
            "provider_tripwire_calls": 0,
            "oracle_self_checks": [oracle_probe],
            "correctness": "full persisted records, exact transcript quotes, preview digest, score oracle, replay, concurrency, and invalid no-preview match independent expectations",
        }


def main(repeats=5, json_output=None):
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    run_trial(2)  # correctness warm-up excluded from reported runs
    runs = []
    for count in (24, 64):
        trials = [run_trial(count) for _ in range(repeats)]
        durations = sorted(item["host_preview_and_approved_create_seconds"] for item in trials)
        state_durations = sorted(item["signed_state_transition_seconds"] for item in trials)
        result = dict(trials[-1])
        result["host_preview_and_approved_create_p50_seconds"] = round(durations[len(durations) // 2], 6)
        result["host_preview_and_approved_create_p95_seconds"] = round(durations[-1], 6)
        result["signed_state_transition_p50_seconds"] = round(state_durations[len(state_durations) // 2], 6)
        result["signed_state_transition_p95_seconds"] = round(state_durations[-1], 6)
        result["warmup_trials_excluded"] = 1
        runs.append(result)
    emit({
        "benchmark": "study_agent_branch_exam_host_flow",
        "seed": SEED,
        "ai_included": False,
        "provider_execution": "excluded; every AIService provider entry point is fail-fast patched",
        "runs": runs,
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
