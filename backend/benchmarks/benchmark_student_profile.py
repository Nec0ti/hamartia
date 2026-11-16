"""Persisted local student-profile benchmark; no provider or network calls."""

import argparse
import json
import socket
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import student_profile
from app.models.schemas import StudentOnboarding
from app.services.ai_service import AIService
from app.services.backup import create_backup, extract_backup
from benchmark_common import assert_oracle, emit, probe_oracle_self_check

REPEATS = 21


def fixture(index, revision=0):
    return {
        "revision": revision,
        "tutorial_completed": True, "tutorial_skipped": False, "survey_completed": True,
        "profile": {
            "nickname": f"Synthetic learner {index}", "age_years": 17, "grade_year": "11",
            "curriculum": "Synthetic custom curriculum", "study_preferences": "Short focused sessions",
            "study_goals": "Review algebra", "avatar_preset": "moon",
        },
    }


def timed(operation, repeats):
    operation()
    values = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        values.append(time.perf_counter() - started)
    ordered = sorted(values)
    return {
        "samples": repeats, "warmups": 1,
        "p50_seconds": round(statistics.median(values), 6),
        "p95_seconds": round(ordered[(repeats * 95 + 99) // 100 - 1], 6),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    if not 3 <= args.repeats <= 1000:
        raise SystemExit("--repeats must be 3..1000")

    with tempfile.TemporaryDirectory(prefix="hamartia-student-profile-bench-") as temp:
        root = Path(temp)
        data_dir = root / "data"
        oracle_count = 0

        def check(actual, expected, label):
            nonlocal oracle_count
            assert_oracle(actual, expected, label)
            oracle_count += 1

        app = FastAPI()
        app.include_router(student_profile.router)
        with ExitStack() as stack:
            stack.enter_context(patch.object(student_profile, "DATA_DIR", data_dir))
            for method in ("analyze_question", "study_chat", "study_practice_prepare", "study_learning_evidence_prepare",
                           "study_question_prepare", "study_exam_prepare", "study_sectioned_exam_prepare"):
                stack.enter_context(patch.object(AIService, method, side_effect=AssertionError(f"provider tripwire: {method}")))
            stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("network tripwire")))
            with TestClient(app) as client:
                empty = StudentOnboarding().model_dump(mode="json")
                check(client.get("/student-profile").json(), empty, "empty full-row oracle")

                revision = 0
                initial = fixture(0, revision)
                first_saved = {**initial, "revision": 1}
                check(client.put("/student-profile", json=initial).json(), first_saved, "initial save full-row oracle")
                revision = 1

                def save_profile():
                    nonlocal revision
                    payload = fixture(0, revision)
                    revision += 1
                    check(client.put("/student-profile", json=payload).json(), {**payload, "revision": revision}, "save full-row oracle")

                save_timing = timed(save_profile, args.repeats)
                expected_saved = {**fixture(0, revision - 1), "revision": revision}
                read_timing = timed(lambda: check(client.get("/student-profile").json(), expected_saved, "read full-row oracle"), args.repeats)

                def update_profile():
                    nonlocal revision
                    payload = fixture(1, revision)
                    revision += 1
                    check(client.put("/student-profile", json=payload).json(), {**payload, "revision": revision}, "update full-row oracle")

                update_timing = timed(update_profile, args.repeats)
                current_row = client.get("/student-profile").json()
                invalid = {**current_row, "profile": {**current_row["profile"], "birth_date": "2009-01-01"}}
                invalid_response = client.put("/student-profile", json=invalid)
                if invalid_response.status_code != 422:
                    raise AssertionError("malformed profile was not rejected")
                check(client.get("/student-profile").json(), current_row, "malformed update preserved full row")

                stale = fixture(99, revision - 1)
                if client.put("/student-profile", json=stale).status_code != 409:
                    raise AssertionError("stale profile update was not rejected")
                check(client.get("/student-profile").json(), current_row, "stale update preserved full row")

                contenders = [fixture(index + 10, revision) for index in range(24)]
                with ThreadPoolExecutor(max_workers=8) as pool:
                    responses = list(pool.map(lambda value: client.put("/student-profile", json=value), contenders))
                if sum(response.status_code == 200 for response in responses) != 1 or sum(response.status_code == 409 for response in responses) != len(contenders) - 1:
                    raise AssertionError("competing writes did not accept exactly one current-revision request")
                revision += 1
                for response, expected in zip(responses, contenders):
                    if response.status_code == 200:
                        check(response.json(), {**expected, "revision": revision}, "competing update response full-row oracle")
                final = client.get("/student-profile").json()
                if final not in [{**row, "revision": revision} for row in contenders]:
                    raise AssertionError("competing full-document update did not persist one exact contender row")
                check(json.loads((data_dir / "onboarding.json").read_text(encoding="utf-8")), final,
                              "competing persisted full-row oracle")

                archive = root / "profile.zip"
                backup_timing = timed(lambda: create_backup(data_dir, archive), args.repeats)
                restored_dir = root / "restored"
                extract_backup(archive, restored_dir)
                check(json.loads((restored_dir / "onboarding.json").read_text(encoding="utf-8")), final,
                              "backup restore full-row oracle")

                def reset_profile():
                    nonlocal revision
                    revision += 1
                    expected_reset = {"revision": revision, "tutorial_completed": False, "tutorial_skipped": False,
                                      "survey_completed": False, "profile": {key: None for key in final["profile"]}}
                    check(client.delete("/student-profile").json(), expected_reset, "reset full-row oracle")

                reset_timing = timed(reset_profile, args.repeats)
                expected_reset = {"revision": revision, "tutorial_completed": False, "tutorial_skipped": False,
                                  "survey_completed": False, "profile": {key: None for key in final["profile"]}}
                check(client.get("/student-profile").json(), expected_reset, "persisted reset full-row oracle")
                if client.put("/student-profile", json=final).status_code != 409:
                    raise AssertionError("pre-reset profile replay was not rejected as stale")
                check(client.get("/student-profile").json(), expected_reset, "stale post-reset write preserved empty profile")

                probe_oracle_self_check(final, final, lambda row: row["profile"].__setitem__("nickname", "wrong"),
                                        "profile full-row comparator rejects perturbed nickname")
                result = {
                    "benchmark": "persisted-local-student-profile-v1",
                    "repeats": args.repeats,
                    "full_row_oracles": oracle_count,
                    "competing_updates": len(contenders),
                    "malformed_updates_rejected": 1,
                    "stale_updates_rejected": 1,
                    "backup_round_trip": True,
                    "reset_round_trip": True,
                    "provider_tripwire_calls": 0,
                    "network_tripwire_calls": 0,
                    "measurements": {"save": save_timing, "read": read_timing, "update": update_timing, "backup": backup_timing, "reset": reset_timing},
                }
    emit(result, args.json_output)


if __name__ == "__main__":
    main()
