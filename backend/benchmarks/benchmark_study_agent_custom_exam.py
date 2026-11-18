"""Adversarial, deterministic host-only benchmark for user-defined mock capture.

No model/provider or network is used. The fixture deliberately exercises the
maximum supported 12-section shape, non-ASCII labels, exact rational scoring,
quote binding, replay safety, and the complete persisted record oracle.
"""

import argparse
import asyncio
import json
import tempfile
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import exams
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Exam, ExamScoringProfile, ExamScoringRule
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_custom_exam import MAX_SECTIONS
from benchmark_common import assert_oracle, emit, probe_oracle_self_check
from benchmark_network_guard import loopback_only

SEED = 20261119
PROFILE = ExamScoringProfile(profile_id="bench-custom-exact", version=9, display_name="Synthetic exact scoring",
    country_label="User supplied", scoring_rule=ExamScoringRule(correct_points="7/3", wrong_penalty="2/5", blank_points="1/7"))


def host_tripwires():
    stack = ExitStack()
    stack.enter_context(loopback_only())
    for name in ("analyze_question", "study_chat", "study_practice_prepare", "study_learning_evidence_prepare",
                 "study_question_prepare", "study_exam_prepare", "study_sectioned_exam_prepare", "study_custom_exam_prepare"):
        if hasattr(AIService, name):
            stack.enter_context(patch.object(AIService, name, side_effect=AssertionError(f"provider execution in benchmark: {name}")))
    return stack


def run_trial():
    with tempfile.TemporaryDirectory(prefix="hamartia-custom-exam-bench-") as temp, host_tripwires():
        root = Path(temp)
        storage = StorageService(root)
        storage.append_list("exam_profiles.json", PROFILE, ExamScoringProfile)
        app = FastAPI()
        app.add_exception_handler(Exception, safe_validation_error_handler)
        app.include_router(exams.router)
        with patch.object(exams, "DATA_DIR", root), TestClient(app) as client:
            fields = ["format_name", "date", "duration_minutes", "duration_seconds", "section_count"] + [
                f"section_{number}_{field}" for number in range(1, MAX_SECTIONS + 1)
                for field in ("subject", "correct", "incorrect", "blank")]
            values = ["Regional practice · 2030", "2026-11-19", "155", "37", str(MAX_SECTIONS)]
            sections = []
            for number in range(1, MAX_SECTIONS + 1):
                label = f"Section {number:02d} — Δ topic {number * 17}"
                correct, incorrect, blank = (number * 3) % 47, (number * 5) % 19, (number * 7) % 13
                sections.append({"subject": label, "correct": correct, "incorrect": incorrect, "blank": blank})
                values.extend([label, str(correct), str(incorrect), str(blank)])
            messages, token, draft = [], None, None
            started = time.perf_counter()
            for field, value in zip(fields, values, strict=True):
                messages.append(value)
                response = client.post("/exams/custom-sectioned-agent-draft", json={
                    "messages": messages, "language": "en", "expected_exam_field": field,
                    "state_token": token, "scoring_profile_id": PROFILE.profile_id,
                    "scoring_profile_version": PROFILE.version,
                    "evidence_claims": [{"field": field, "quote": value}],
                })
                if response.status_code != 200:
                    raise AssertionError(f"custom host draft rejected fixture field {field}: {response.text}")
                draft = response.json()
                token = draft["state_token"]
                if draft["status"] != ("ready" if field == fields[-1] else "incomplete"):
                    raise AssertionError(f"unexpected progress state at {field}")
            elapsed = time.perf_counter() - started
            expected_correct = sum(row["correct"] for row in sections)
            expected_incorrect = sum(row["incorrect"] for row in sections)
            expected_blank = sum(row["blank"] for row in sections)
            if draft["fields"]["sections"] != sections or (
                draft["fields"]["correct"], draft["fields"]["incorrect"], draft["fields"]["blank"]
            ) != (expected_correct, expected_incorrect, expected_blank):
                raise AssertionError("section identity or aggregate oracle mismatch")
            exact_net = expected_correct * 7 / 3 - expected_incorrect * 2 / 5 + expected_blank / 7
            if abs(draft["derived"]["net"] - exact_net) > 1e-10 or draft["scoring_profile_snapshot"] != PROFILE.model_dump():
                raise AssertionError("custom immutable scoring snapshot/net oracle mismatch")
            body = {
                "messages": messages, "language": "en", "expected_exam_field": fields[-1], "state_token": None,
                "scoring_profile_id": PROFILE.profile_id, "scoring_profile_version": PROFILE.version,
                "evidence_claims": draft["evidence_claims"], "fields": draft["fields"],
                "evidence": draft["verified_evidence"], "scoring_profile_snapshot": draft["scoring_profile_snapshot"],
                "derived": draft["derived"], "preview_digest": draft["preview_digest"], "approval_id": str(uuid.uuid4()),
            }
            created = client.post("/exams/custom-sectioned-agent-create", json=body)
            if created.status_code != 201:
                raise AssertionError(f"custom explicit approval failed: {created.text}")
            replay = client.post("/exams/custom-sectioned-agent-create", json=body)
            if replay.json() != created.json():
                raise AssertionError("identical approval did not converge idempotently")
            altered = json.loads(json.dumps(body))
            altered["fields"]["sections"][0]["subject"] = "mutated label"
            if client.post("/exams/custom-sectioned-agent-create", json=altered).status_code != 409:
                raise AssertionError("changed approval replay was not rejected")
            incomplete = client.post("/exams/custom-sectioned-agent-draft", json={
                "messages": ["Maybe some format"], "language": "en", "expected_exam_field": "format_name",
                "state_token": None, "scoring_profile_id": PROFILE.profile_id,
                "scoring_profile_version": PROFILE.version, "evidence_claims": [{"field": "format_name", "quote": "Maybe some format"}],
            }).json()
            if incomplete["status"] != "ambiguous" or len(storage.load_list("exams.json", Exam)) != 1:
                raise AssertionError("ambiguous evidence wrote data or was accepted")
            row = created.json()
            expected = [{key: row[key] for key in row}]
            actual = [record.model_dump(mode="json") for record in storage.load_list("exams.json", Exam)]
            assert_oracle(actual, expected, "custom exam persisted complete row")
            probes = [
                probe_oracle_self_check(actual, expected, lambda rows: rows[0].__setitem__("format_name", "invented"), "format name corruption"),
                probe_oracle_self_check(actual, expected, lambda rows: rows[0].__setitem__("sections", []), "section roster corruption"),
                probe_oracle_self_check(actual, expected, lambda rows: rows[0].__setitem__("net", 999), "score corruption"),
            ]
            return {"seed": SEED, "fixture_sections": MAX_SECTIONS, "fixture_fields": len(fields),
                    "approval_rows": len(actual), "idempotent_retry": True, "altered_replay_rejected": True,
                    "ambiguous_no_write": True, "oracle_self_checks": probes, "capture_approval_seconds": round(elapsed, 6)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be between 1 and 20")
    results = [run_trial() for _ in range(args.repeats)]
    emit({"benchmark": "custom-sectioned-exam-host-capture", "seed": SEED, "repeats": results,
          "ai_included": False, "provider_execution": False, "network_allowed": False}, args.json)


if __name__ == "__main__":
    main()
