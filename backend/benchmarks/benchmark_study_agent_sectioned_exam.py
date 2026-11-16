"""Persisted host-only benchmark for sectioned TYT/AYT Study Agent capture."""

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api import exams
from app.models.schemas import Exam, ExamScoringProfile, ExamScoringRule
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_sectioned_exam import STATIC_FIELDS, SECTION_FIELDS, STATE_LOCK, STATE_USED, SectionedExamQuote, prepare_capture, resolve_state_token
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

SEED = 20261116
LIVE_STATE_TOKENS = 0
PROFILE = ExamScoringProfile(
    profile_id="benchmark-sectioned", version=3, display_name="Benchmark exact rule", country_label="Synthetic",
    scoring_rule=ExamScoringRule(correct_points="3/2", wrong_penalty="1/3", blank_points="1/10"),
)


def fixture(index: int):
    section_count = 1 + index % 6
    values = ["TYT" if index % 2 == 0 else "AYT", f"2026-11-{index % 28 + 1:02d}", str(35 + index % 150), str(index % 60), str(section_count)]
    sections = []
    for number in range(1, section_count + 1):
        sections.append({
            "subject": f"Synthetic Subject {index:04d}-{number}",
            "correct": str((index + number) % 41),
            "incorrect": str((index * 2 + number) % 13),
            "blank": str((index + number * 3) % 9),
        })
        values.extend(sections[-1][field] for field in SECTION_FIELDS)
    fields = list(STATIC_FIELDS) + [f"section_{number}_{field}" for number in range(1, section_count + 1) for field in SECTION_FIELDS]
    messages = list(values)
    claims = [{"field": field, "quote": quote} for field, quote in zip(fields, values, strict=True)]
    return messages, claims, sections, fields


def expected_fields(messages, sections, profile):
    sections = [{"subject": section["subject"], **{field: int(section[field]) for field in ("correct", "incorrect", "blank")}} for section in sections]
    correct = sum(section["correct"] for section in sections)
    incorrect = sum(section["incorrect"] for section in sections)
    blank = sum(section["blank"] for section in sections)
    return {
        "date": messages[1], "exam_type": messages[0].lower(),
        "subject": f"{messages[0].upper()} Geneli", "correct": correct, "incorrect": incorrect, "blank": blank,
        "duration_minutes": int(messages[2]), "duration_seconds": int(messages[3]),
        "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version,
        "sections": sections,
    }


def expected_derived(fields, profile):
    exact_net = (
        fields["correct"] * Fraction(profile.scoring_rule.correct_points)
        - fields["incorrect"] * Fraction(profile.scoring_rule.wrong_penalty)
        + fields["blank"] * Fraction(profile.scoring_rule.blank_points)
    )
    legacy_net = fields["correct"] - fields["incorrect"] / 4
    duration = fields["duration_minutes"] or 1
    xp = max(0, int(legacy_net * fields["correct"] * 1.5 - duration * fields["incorrect"] * 0.25))
    return {"net": float(exact_net), "xp": xp}


def digest(fields, evidence, profile, derived):
    raw = json.dumps({"fields": fields, "evidence": evidence, "scoring_profile_snapshot": profile.model_dump(), "derived": derived},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def preview(messages, claims, storage, profile):
    global LIVE_STATE_TOKENS
    token = None
    draft = None
    for position, claim in enumerate(claims):
        current_messages = messages[:position + 1]
        if token:
            prior = resolve_state_token(token, current_messages, "en", profile)
            LIVE_STATE_TOKENS -= 1
        else:
            prior = []
        if claim["field"] != (list(STATIC_FIELDS) + [f"section_{number}_{name}" for number in range(1, int(messages[4]) + 1) for name in SECTION_FIELDS])[len(prior)]:
            raise AssertionError("fixture field order differs from host order")
        draft = prepare_capture(current_messages, "en", prior, [SectionedExamQuote.model_validate(claim)], profile)
        if draft["status"] != "ready":
            token_messages = current_messages
            from app.services.study_agent_sectioned_exam import issue_state_token
            token = issue_state_token(token_messages, "en", draft["evidence_claims"], profile)
            LIVE_STATE_TOKENS += 1
        else:
            token = None
    if token is not None:
        raise AssertionError("completed preview left an unconsumed continuation token")
    return draft


def approval_body(index, messages, claims, draft, profile):
    return {
        "messages": messages, "language": "en", "expected_exam_field": claims[-1]["field"], "state_token": None,
        "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version,
        "evidence_claims": draft["evidence_claims"], "fields": draft["fields"],
        "evidence": draft["verified_evidence"], "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
        "derived": draft["derived"], "preview_digest": draft["preview_digest"],
        "approval_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sectioned-exam:{index}")),
    }


def fingerprint(body):
    fingerprint_body = {key: body[key] for key in (
        "messages", "language", "expected_exam_field", "evidence_claims", "fields", "evidence",
        "scoring_profile_snapshot", "derived", "preview_digest",
    )}
    raw = json.dumps(fingerprint_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def provider_tripwires():
    stack = ExitStack()
    for name in ("analyze_question", "study_chat", "study_practice_prepare", "study_learning_evidence_prepare",
                 "study_question_prepare", "study_exam_prepare", "study_sectioned_exam_prepare"):
        stack.enter_context(patch.object(AIService, name, side_effect=AssertionError(f"provider call during host benchmark: {name}")))
    return stack


def run_trial(count):
    global LIVE_STATE_TOKENS
    # Each trial uses fresh, completed conversations. Their continuation tokens
    # are all consumed before this boundary; only consumed replay keys are reset.
    if LIVE_STATE_TOKENS != 0:
        raise AssertionError("cannot reset replay cache while any continuation token is live")
    with STATE_LOCK:
        STATE_USED.clear()
    with tempfile.TemporaryDirectory(prefix="hamartia-sectioned-exam-bench-") as directory, provider_tripwires():
        storage = StorageService(Path(directory))
        storage.append_list("exam_profiles.json", PROFILE, ExamScoringProfile)
        expected_rows = []
        timed_start = time.perf_counter()
        first_body = None
        for index in range(count):
            messages, claims, sections, _ = fixture(index)
            draft = preview(messages, claims, storage, PROFILE)
            fields = expected_fields(messages, sections, PROFILE)
            evidence = {claim["field"]: {"quote": claim["quote"], "message_index": position}
                        for position, claim in enumerate(claims)}
            derived = expected_derived(fields, PROFILE)
            if draft["status"] != "ready" or draft["fields"] != fields or draft["verified_evidence"] != evidence or draft["derived"] != derived:
                raise AssertionError("host sectioned preview differs from independent sections/totals/profile/net/XP oracle")
            if draft["preview_digest"] != digest(fields, evidence, PROFILE, derived):
                raise AssertionError("canonical preview digest differs from independent oracle")
            body = approval_body(index, messages, claims, draft, PROFILE)
            record = asyncio.run(exams.sectioned_exam_agent_create(exams.SectionedExamCreateRequest.model_validate(body), storage))
            expected_id = f"sectioned_exam_agent_{uuid.UUID(body['approval_id']).hex}_{fingerprint(body)}"
            if record.id != expected_id:
                raise AssertionError("approval ID differs from independent exact-body fingerprint")
            expected_record = {
                "id": expected_id, **{key: value for key, value in fields.items() if key not in {"scoring_profile_id", "scoring_profile_version"}},
                "created_at": record.created_at, "scoring_profile": PROFILE.model_dump(),
                "total": fields["correct"] + fields["incorrect"], "net": derived["net"], "xp": derived["xp"],
            }
            if record.model_dump() != expected_record:
                raise AssertionError("persisted row differs from full independent field/profile/score oracle")
            expected_rows.append(expected_record)
            if index == 0:
                first_body = body
        timed_seconds = time.perf_counter() - timed_start

        # Cancel/no-approval and rejection probes are outside the timed section.
        cancel_messages = ["TYT"]
        cancelled = prepare_capture(cancel_messages, "en", [], [{"field": "exam_type", "quote": "TYT"}], PROFILE)
        if cancelled["status"] != "incomplete" or cancelled["preview_digest"] is not None or len(storage.load_list("exams.json", Exam)) != count:
            raise AssertionError("cancelled incomplete draft created a record or an approvable preview")
        replay = asyncio.run(exams.sectioned_exam_agent_create(exams.SectionedExamCreateRequest.model_validate(first_body), storage))
        if replay.id != expected_rows[0]["id"]:
            raise AssertionError("same-body retry did not return its original sectioned exam")
        altered = json.loads(json.dumps(first_body))
        altered["fields"]["date"] = "2026-12-01"
        try:
            asyncio.run(exams.sectioned_exam_agent_create(exams.SectionedExamCreateRequest.model_validate(altered), storage))
        except HTTPException as exc:
            if exc.status_code != 409:
                raise AssertionError("changed approval retry did not return conflict") from exc
        else:
            raise AssertionError("changed approval retry unexpectedly succeeded")

        messages, claims, sections, _ = fixture(10_000)
        concurrent_draft = preview(messages, claims, storage, PROFILE)
        body = approval_body(10_000, messages, claims, concurrent_draft, PROFILE)
        request = exams.SectionedExamCreateRequest.model_validate(body)
        started_concurrent = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            concurrent = list(pool.map(lambda _: asyncio.run(exams.sectioned_exam_agent_create(request, storage)), range(8)))
        concurrent_seconds = time.perf_counter() - started_concurrent
        if len({record.id for record in concurrent}) != 1:
            raise AssertionError("concurrent identical approvals did not converge on one record")
        fields = expected_fields(messages, sections, PROFILE)
        derived = expected_derived(fields, PROFILE)
        expected_concurrent = {
            "id": concurrent[0].id, **{key: value for key, value in fields.items() if key not in {"scoring_profile_id", "scoring_profile_version"}},
            "created_at": concurrent[0].created_at, "scoring_profile": PROFILE.model_dump(),
            "total": fields["correct"] + fields["incorrect"], "net": derived["net"], "xp": derived["xp"],
        }
        if concurrent[0].model_dump() != expected_concurrent:
            raise AssertionError("concurrent row differs from independent full-row oracle")
        expected_rows.append(expected_concurrent)

        persisted = storage.load_list("exams.json", Exam)
        actual_rows = [row.model_dump() for row in persisted]
        assert_oracle(actual_rows, expected_rows, "sectioned-exam persisted full rows")
        # Deterministic wrong-result probes run after all timing has stopped.
        probes = [
            probe_oracle_self_check(actual_rows, expected_rows, lambda rows: rows[0].__setitem__("sections", []), "section roster corruption"),
            probe_oracle_self_check(actual_rows, expected_rows, lambda rows: rows[0].__setitem__("correct", -1), "aggregate corruption"),
            probe_oracle_self_check(actual_rows, expected_rows, lambda rows: rows[0].__setitem__("scoring_profile", {}), "profile snapshot corruption"),
            probe_oracle_self_check(actual_rows, expected_rows, lambda rows: rows[0].__setitem__("net", 999), "net corruption"),
            probe_oracle_self_check(actual_rows, expected_rows, lambda rows: rows[0].__setitem__("xp", 999), "XP corruption"),
        ]
        if len(actual_rows) != count + 1:
            raise AssertionError("cancel, retry, changed retry, or concurrent create changed expected row count")
        # Keep this capacity check outside the timed interval so churn or cache
        # growth beyond the host's fixed 4096-entry bound remains visible.
        with STATE_LOCK:
            replay_cache_entries = len(STATE_USED)
        if replay_cache_entries > 4096:
            raise AssertionError("used continuation replay cache exceeded its fixed capacity")
        if LIVE_STATE_TOKENS != 0:
            raise AssertionError("trial ended with a live continuation token")
        return {
            "records": count,
            "host_preview_and_approved_create_seconds": round(timed_seconds, 6),
            "records_per_second": round(count / timed_seconds, 2) if timed_seconds else None,
            "persisted_bytes": (Path(directory) / "exams.json").stat().st_size,
            "sections_checked": sum(len(fixture(index)[2]) for index in range(count)) + len(sections),
            "cancelled_no_write": True, "same_body_retries": 1, "changed_replay_conflicts": 1,
            "concurrent_approval_requests": 8, "concurrent_approval_rows": 1,
            "concurrent_approval_seconds": round(concurrent_seconds, 6),
            "provider_tripwire_calls": 0, "wrong_result_probes": probes,
            "used_replay_cache_entries": replay_cache_entries, "used_replay_cache_capacity": 4096,
            "correctness": "full persisted rows, section order, aggregate totals, profile snapshot, net/XP, digest, approval retries, and race match independent expectations",
        }


def main(repeats=3, json_output=None):
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    run_trial(2)
    runs = []
    for count in (24, 64):
        trials = [run_trial(count) for _ in range(repeats)]
        durations = sorted(item["host_preview_and_approved_create_seconds"] for item in trials)
        result = dict(trials[-1])
        result["host_preview_and_approved_create_p50_seconds"] = round(durations[len(durations) // 2], 6)
        result["host_preview_and_approved_create_p95_seconds"] = round(durations[-1], 6)
        result["warmup_trials_excluded"] = 1
        runs.append(result)
    emit({
        "benchmark": "study_agent_sectioned_exam_host_flow", "seed": SEED, "ai_included": False,
        "provider_execution": "excluded; every AIService provider entry point is fail-fast patched",
        "external_browser_requests": "not part of this host benchmark; the separate Playwright smoke asserts none",
        "runs": runs,
    }, json_output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
