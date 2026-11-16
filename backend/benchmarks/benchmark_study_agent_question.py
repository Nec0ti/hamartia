"""Benchmark deterministic host question-capture preview/create, without either provider."""

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

from app.api import questions
from app.models.schemas import Question
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_question import (
    issue_question_state_token,
    prepare_question_capture,
    resolve_question_state_token,
)
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

SEED = 20261116


def fixture(index: int):
    text = f"If a rectangle has width {index + 2} cm and length {index + 5} cm, what is its area?"
    subject = f"Synthetic subject {index % 9:02d}"
    topic = f"Synthetic topic {index % 17:02d}"
    messages = [text, subject, topic]
    claims = [{"field": field, "quote": quote} for field, quote in zip(("question_text", "subject", "topic"), messages)]
    fields = {"question_text": text, "subject": subject, "topic": topic}
    return messages, claims, fields


def expected_evidence(messages, claims, fields):
    result = {}
    for claim in claims:
        matches = []
        quote = claim["quote"]
        for index, message in enumerate(messages):
            start = message.find(quote)
            while start >= 0:
                matches.append((index, start))
                start = message.find(quote, start + 1)
        if len(matches) != 1:
            raise AssertionError("benchmark quote must occur once in the synthetic transcript")
        message_index, start = matches[0]
        result[claim["field"]] = {
            "value": fields[claim["field"]], "message_index": message_index,
            "quote": quote, "start": start, "end": start + len(quote), "skipped": False,
        }
    return result


def approval_fingerprint(body):
    approved = {key: value for key, value in body.items() if key != "approval_id"}
    encoded = json.dumps(approved, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provider_tripwires():
    """Make the configured-provider host entry fail immediately if the benchmark reaches it."""
    stack = ExitStack()
    for name in ("study_chat", "study_practice_prepare", "study_learning_evidence_prepare", "study_question_prepare"):
        stack.enter_context(patch.object(AIService, name, side_effect=AssertionError(f"AI/provider call during host benchmark: {name}")))
    return stack


def sequential_draft(messages, claims, language="en"):
    """Exercise the real host route and one-use transcript token at each expected turn."""
    token = None
    draft = None
    for index, field in enumerate(("question_text", "subject", "topic")):
        draft = asyncio.run(questions.question_agent_draft(questions.AgentQuestionDraftRequest(
            messages=messages[:index + 1], language=language,
            expected_question_field=field, state_token=token,
            evidence_claims=[claims[index]],
        )))
        if index < 2:
            if draft["status"] != "incomplete" or draft["expected_field"] != ("subject" if index == 0 else "topic"):
                raise AssertionError("host question follow-up did not advance in its fixed field order")
            token = draft["state_token"]
    return draft


def preview_and_create(index, storage):
    messages, claims, fields = fixture(index)
    draft = sequential_draft(messages, claims)
    expected = expected_evidence(messages, claims, fields)
    if draft["status"] != "ready" or draft["fields"] != fields or draft["verified_evidence"] != expected:
        raise AssertionError("host question preview differs from independent fixture oracle")
    canonical = json.dumps({"messages": messages, "language": "en", "fields": fields, "evidence": expected},
                           ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if draft["preview_digest"] != hashlib.sha256(canonical).hexdigest():
        raise AssertionError("question preview digest differs from independent canonical snapshot")
    approval_id = uuid.uuid5(uuid.NAMESPACE_URL, f"question-capture:{index}")
    body = {
        "messages": messages, "language": "en", "evidence_claims": claims,
        "fields": fields, "evidence": expected, "preview_digest": draft["preview_digest"],
        "approval_id": str(approval_id),
    }
    request = questions.AgentQuestionCreateRequest.model_validate(body)
    record = asyncio.run(questions.question_agent_create(request, storage))
    expected_id = f"q_agent_{approval_id.hex}_{approval_fingerprint(body)}"
    if record.id != expected_id:
        raise AssertionError("saved question ID differs from independent approval fingerprint")
    expected_row = {"ocr_text": fields["question_text"], "subject": fields["subject"],
                    "topic": fields["topic"], "id": expected_id, "created_at": record.created_at}
    return record, expected_row, body


def signed_skip_transition(index):
    text = f"A triangle has sides {index + 2}, 4, and 5. Find its perimeter."
    prefix = [text, "atla"]
    prior_claims = [{"field": "question_text", "quote": text}, {"field": "subject", "quote": "atla"}]
    prior = prepare_question_capture(prefix, "tr", prior_claims)
    if prior["expected_field"] != "topic" or prior["status"] != "incomplete":
        raise AssertionError("host prior state did not select topic after subject skip")
    token = issue_question_state_token(prefix, "tr", prior["verified_evidence"])
    messages = [*prefix, "atla"]
    resolved = resolve_question_state_token(token, messages, "tr")
    prepared = prepare_question_capture(messages, "tr", [*resolved, {"field": "topic", "quote": "atla"}])
    if prepared["status"] != "ready" or prepared["fields"] != {"question_text": text, "subject": "", "topic": ""}:
        raise AssertionError("repeated explicit skip did not produce the expected blank optional fields")
    try:
        resolve_question_state_token(token, messages, "tr")
    except ValueError:
        pass
    else:
        raise AssertionError("one-use question state token replay was accepted")


def run_trial(count):
    with tempfile.TemporaryDirectory(prefix="hamartia-question-agent-bench-") as directory, provider_tripwires():
        storage = StorageService(Path(directory))
        state_count = 100
        state_started = time.perf_counter()
        for index in range(state_count):
            signed_skip_transition(index)
        state_elapsed = time.perf_counter() - state_started

        started = time.perf_counter()
        expected_rows, bodies = [], []
        for index in range(count):
            _, expected_row, body = preview_and_create(index, storage)
            expected_rows.append(expected_row)
            bodies.append(body)
        elapsed = time.perf_counter() - started

        # Exact retry is idempotent; the same approval UUID with an altered body conflicts.
        same = asyncio.run(questions.question_agent_create(
            questions.AgentQuestionCreateRequest.model_validate(bodies[0]), storage,
        ))
        if same.id != expected_rows[0]["id"]:
            raise AssertionError("exact approval retry did not return the original row")
        changed = json.loads(json.dumps(bodies[0]))
        changed["fields"]["topic"] += " changed"
        try:
            asyncio.run(questions.question_agent_create(questions.AgentQuestionCreateRequest.model_validate(changed), storage))
        except HTTPException as error:
            if error.status_code != 409:
                raise AssertionError("altered approval replay did not return 409") from error
        else:
            raise AssertionError("altered approval replay unexpectedly created a row")

        concurrent_messages, concurrent_claims, concurrent_fields = fixture(10_000)
        concurrent_draft = sequential_draft(concurrent_messages, concurrent_claims)
        concurrent_evidence = expected_evidence(concurrent_messages, concurrent_claims, concurrent_fields)
        concurrent_approval = str(uuid.uuid5(uuid.NAMESPACE_URL, "question-capture:concurrent"))
        concurrent_body = {
            "messages": concurrent_messages, "language": "en", "evidence_claims": concurrent_claims,
            "fields": concurrent_fields, "evidence": concurrent_evidence,
            "preview_digest": concurrent_draft["preview_digest"], "approval_id": concurrent_approval,
        }
        request = questions.AgentQuestionCreateRequest.model_validate(concurrent_body)
        concurrent_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda _: asyncio.run(questions.question_agent_create(request, storage)), range(8)))
        concurrent_elapsed = time.perf_counter() - concurrent_start
        if len({record.id for record in records}) != 1:
            raise AssertionError("concurrent exact approvals created different records")
        expected_rows.append({"ocr_text": concurrent_fields["question_text"], "subject": concurrent_fields["subject"],
                              "topic": concurrent_fields["topic"], "id": records[0].id,
                              "created_at": records[0].created_at})

        # Invalid/missing question text cannot be previewed or written, even with a fabricated approval body.
        invalid_messages = ["Maybe I will add a question later.", "Biology", "Algebra"]
        invalid_claims = [{"field": field, "quote": value} for field, value in zip(("question_text", "subject", "topic"), invalid_messages)]
        invalid_preview = prepare_question_capture(invalid_messages, "en", invalid_claims)
        if invalid_preview["status"] != "ambiguous" or invalid_preview["preview_digest"] is not None:
            raise AssertionError("hypothetical question text received an approvable preview")
        invalid_body = {
            "messages": invalid_messages, "language": "en", "evidence_claims": invalid_claims,
            "fields": {"question_text": invalid_messages[0], "subject": "Biology", "topic": "Algebra"},
            "evidence": {}, "preview_digest": "0" * 64, "approval_id": str(uuid.uuid4()),
        }
        try:
            asyncio.run(questions.question_agent_create(questions.AgentQuestionCreateRequest.model_validate(invalid_body), storage))
        except HTTPException as error:
            if error.status_code != 422:
                raise AssertionError("invalid question create did not fail closed") from error
        else:
            raise AssertionError("invalid question unexpectedly wrote a record")

        persisted = storage.load_list("questions.json", Question)
        if len(persisted) != count + 1:
            raise AssertionError("replay or invalid evidence changed the persisted question count")
        actual = [{"id": row.id, "ocr_text": row.ocr_text, "subject": row.subject,
                   "topic": row.topic, "created_at": row.created_at} for row in persisted]
        assert_oracle(actual, expected_rows, "question full persisted text/labels")
        oracle_probe = probe_oracle_self_check(actual, expected_rows,
                                               lambda rows: rows[0].__setitem__("subject", "corrupted"),
                                               "question subject corrupted")

        # Deletion remains effective and the UUID-only tombstone prevents the same approval from recreating it.
        deleted = persisted[-1]
        asyncio.run(questions.delete_question(deleted.id, storage))
        try:
            asyncio.run(questions.question_agent_create(
                questions.AgentQuestionCreateRequest.model_validate(concurrent_body), storage,
            ))
        except HTTPException as error:
            if error.status_code != 409:
                raise AssertionError("post-delete replay did not return 409") from error
        else:
            raise AssertionError("post-delete approval replay recreated the deleted row")
        if len(storage.load_list("questions.json", Question)) != count:
            raise AssertionError("post-delete replay changed the remaining row count")

        return {
            "records": count,
            "signed_repeated_skip_transitions": state_count,
            "signed_state_transition_seconds": round(state_elapsed, 6),
            "signed_state_transitions_per_second": round(state_count / state_elapsed, 2) if state_elapsed else None,
            "preview_and_create_seconds": round(elapsed, 6),
            "records_per_second": round(count / elapsed, 2) if elapsed else None,
            "persisted_bytes": (Path(directory) / "questions.json").stat().st_size,
            "exact_retries": 1,
            "altered_replay_conflicts": 1,
            "concurrent_same_approval_requests": len(records),
            "concurrent_unique_records": 1,
            "invalid_hypothetical_writes": 0,
            "post_delete_replay_writes": 0,
            "provider_tripwire_calls": 0,
            "ai_included": False,
            "oracle_self_checks": [oracle_probe],
            "correctness": "exact whole-turn provenance, canonical digest and ID, signed one-use transitions, repeated optional skips, idempotent retries, conflicts, invalid no-write, and deleted-row replay match independent oracles",
        }


def main(repeats=5, json_output=None):
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    run_trial(2)
    runs = []
    for count in (24, 64):
        trials = [run_trial(count) for _ in range(repeats)]
        durations = sorted(item["preview_and_create_seconds"] for item in trials)
        result = dict(trials[-1])
        result["preview_and_create_p50_seconds"] = round(durations[len(durations) // 2], 6)
        result["preview_and_create_p95_seconds"] = round(durations[-1], 6)
        runs.append(result)
    emit({
        "benchmark": "study_agent_question_capture_host_flow", "seed": SEED,
        "provider_execution": "excluded; AIService provider entry points are fail-fast patched; desktop ChatGPT fetch is not imported or invoked",
        "ai_included": False,
        "runs": runs,
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
