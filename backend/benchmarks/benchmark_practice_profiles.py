"""Persisted non-AI oracle for versioned PracticeSession scoring profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import time
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import clock, exam_profiles, practice
from app.models.schemas import ExamScoringProfile, PracticeSession
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService

TODAY = "2026-11-15"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def percentile(samples, value):
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * value))]


def add_profile(client, name, rule):
    response = client.post("/exam-profiles", json={
        "display_name": name, "country_label": "Synthetic benchmark fixture", "scoring_rule": rule,
    })
    require(response.status_code == 201, f"profile create failed: {response.text}")
    profile = response.json()
    require(profile["profile_id"].startswith("profile_") and profile["version"] == 1, "profile reference shape changed")
    return profile


def update_profile(client, profile, name, rule):
    response = client.put(f"/exam-profiles/{profile['profile_id']}", json={
        "display_name": name, "country_label": "Synthetic benchmark fixture", "scoring_rule": rule,
    })
    require(response.status_code == 200, f"profile update failed: {response.text}")
    revised = response.json()
    require(revised["profile_id"] == profile["profile_id"] and revised["version"] == profile["version"] + 1,
            "profile update did not append the next version")
    return revised


def payload(date, subject, topic, correct, incorrect, blank, profile=None, minutes=2, seconds=7):
    result = {
        "date": date, "subject": subject, "topic": topic,
        "correct": correct, "incorrect": incorrect, "blank": blank,
        "duration_minutes": minutes, "duration_seconds": seconds,
    }
    if profile is not None:
        result.update(scoring_profile_id=profile["profile_id"], scoring_profile_version=profile["version"])
    return result


def expected_row(actual, values, profile, net, accuracy):
    """Literal score oracle; identity and timestamp are checked elsewhere as returned metadata."""
    return {
        "id": actual["id"], "created_at": actual["created_at"], **values,
        "scoring_profile": profile, "net": net, "accuracy": accuracy,
    }


def check_full_record(response, expected, label):
    require(response.status_code == 201, f"{label} create failed: {response.text}")
    actual = response.json()
    require(actual == expected, f"{label} API row differs from independent full-row oracle\nactual={actual}\nexpected={expected}")
    require("xp" not in actual, f"{label} practice record unexpectedly received XP")
    return actual


def group_oracle(rows):
    """Rebuild summaries from the independent row table rather than app code."""
    groups = {}
    for row in rows:
        profile = row["scoring_profile"]
        key = (profile["profile_id"], profile["version"], row["subject"].strip().casefold(), row["topic"].strip().casefold())
        groups.setdefault(key, []).append(row)
    result = []
    for key, members in sorted(groups.items(), key=lambda item: (
        item[1][0]["subject"].casefold(), item[1][0]["topic"].casefold(), item[0][0], item[0][1],
    )):
        ordered = sorted(members, key=lambda row: (row["date"], row["created_at"], row["id"]))
        correct = sum(row["correct"] for row in ordered)
        incorrect = sum(row["incorrect"] for row in ordered)
        blank = sum(row["blank"] for row in ordered)
        answered = correct + incorrect
        result.append({
            "subject": ordered[0]["subject"].strip(), "topic": ordered[0]["topic"].strip(),
            "scoring_profile": ordered[0]["scoring_profile"],
            "correct": correct, "incorrect": incorrect, "blank": blank,
            "session_count": len(ordered), "answered": answered,
            "net": sum(row["net"] for row in ordered),
            "accuracy": correct / answered if answered else None,
            "trend": [{"id": row["id"], "date": row["date"], "net": row["net"], "accuracy": row["accuracy"]}
                      for row in ordered],
        })
    return result


def rewrite_as_legacy_archive(source, destination):
    with zipfile.ZipFile(source, "r") as archive:
        files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
        manifest = json.loads(archive.read("manifest.json"))
    files.pop("exam_profiles.json", None)
    sessions = json.loads(files["practice_sessions.json"])
    for record in sessions:
        record.pop("scoring_profile", None)
    files["practice_sessions.json"] = (json.dumps(sessions, ensure_ascii=False, indent=2) + "\n").encode()
    clock_state = json.loads(files["clock.json"])
    if clock_state.get("active_timer"):
        clock_state["active_timer"].get("practice_draft", {}).pop("scoring_profile", None)
    files["clock.json"] = (json.dumps(clock_state, ensure_ascii=False, indent=2) + "\n").encode()
    manifest["files"] = [{
        "path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    } for name, raw in sorted(files.items())]
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        archive.writestr("manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())


def run(repeats=3):
    with tempfile.TemporaryDirectory(prefix="hamartia-practice-profiles-bench-") as temp:
        data_dir = Path(temp) / "data"
        data_dir.mkdir()
        patches = [
            (practice, "DATA_DIR", data_dir),
            (exam_profiles, "DATA_DIR", data_dir),
            (clock, "DATA_DIR", data_dir),
        ]
        originals = [(module, name, getattr(module, name)) for module, name, _ in patches]
        try:
            for module, name, value in patches:
                setattr(module, name, value)
            app = FastAPI()
            app.include_router(exam_profiles.router)
            app.include_router(practice.router)
            app.include_router(clock.router)
            with TestClient(app) as client:
                records = []

                # Invalid/malformed/negative rules are rejected at the catalog boundary.
                for value in ("1/0", "1.5", "-1/4", "not-a-rational"):
                    bad = client.post("/exam-profiles", json={
                        "display_name": "Invalid", "country_label": "Fixture",
                        "scoring_rule": {"correct_points": "1", "wrong_penalty": value, "blank_points": "0"},
                    })
                    require(bad.status_code == 422, f"invalid rational rule was accepted: {value}")
                negative_count = client.post("/practice", json=payload(TODAY, "Boundary", "Negative count", -1, 0, 1))
                zero_questions = client.post("/practice", json=payload(TODAY, "Boundary", "Zero questions", 0, 0, 0))
                sixty_seconds = client.post("/practice", json=payload(TODAY, "Boundary", "Seconds", 1, 0, 0, seconds=60))
                require([negative_count.status_code, zero_questions.status_code, sixty_seconds.status_code] == [422, 422, 422],
                        "negative, zero-question, or invalid-second boundary was accepted")

                half_v1 = add_profile(client, "Half penalty and blank credit", {
                    "correct_points": "1", "wrong_penalty": "1/2", "blank_points": "1/4",
                })
                rational = add_profile(client, "Exact thirds fifths sevenths", {
                    "correct_points": "2/6", "wrong_penalty": "2/10", "blank_points": "1/7",
                })
                require(rational["scoring_rule"] == {
                    "correct_points": "1/3", "wrong_penalty": "1/5", "blank_points": "1/7",
                }, "rational weights did not canonicalize exactly")
                blank_profile = add_profile(client, "Blank credit", {
                    "correct_points": "0", "wrong_penalty": "0", "blank_points": "1/2",
                })

                first_values = payload(TODAY, "Mathematics", "Fractions", 12, 4, 4, half_v1)
                first_response = client.post("/practice", json=first_values)
                first_actual = first_response.json()
                records.append(expected_row(first_actual, {key: value for key, value in first_values.items()
                                                           if key not in ("scoring_profile_id", "scoring_profile_version")},
                                            half_v1, 11.0, 0.75))
                require(first_response.status_code == 201 and first_actual == records[-1], "v1 score or row mismatch")

                half_v2 = update_profile(client, half_v1, "Full penalty", {
                    "correct_points": "1", "wrong_penalty": "1", "blank_points": "0",
                })
                second_values = payload("2026-11-14", "Mathematics", "Fractions", 12, 4, 4, half_v2)
                second_actual = client.post("/practice", json=second_values).json()
                records.append(expected_row(second_actual, {key: value for key, value in second_values.items()
                                                             if key not in ("scoring_profile_id", "scoring_profile_version")},
                                            half_v2, 8.0, 0.75))
                require(second_actual == records[-1], "v2 exact score or row mismatch")

                # Omitted edit selection keeps the original full snapshot after catalog v2 exists.
                edit_values = payload(TODAY, "Mathematics", "Fractions", 10, 4, 4)
                edit_response = client.put(f"/practice/{first_actual['id']}", json=edit_values)
                edited_actual = edit_response.json()
                records[0] = expected_row(edited_actual, edit_values, half_v1, 9.0, 10 / 14)
                require(edit_response.status_code == 200 and edited_actual == records[0], "omitted edit selection did not preserve v1")

                fraction_values = payload("2026-11-13", "Mathematics", "Fractions", 2, 3, 4, rational)
                fraction_actual = client.post("/practice", json=fraction_values).json()
                records.append(expected_row(fraction_actual, {key: value for key, value in fraction_values.items()
                                                              if key not in ("scoring_profile_id", "scoring_profile_version")},
                                            rational, 67 / 105, 0.4))
                require(fraction_actual == records[-1], "exact 67/105 fractional score or answered denominator mismatch")

                blank_values = payload("2026-11-12", "Biology", "Blank only", 0, 0, 4, blank_profile)
                blank_actual = client.post("/practice", json=blank_values).json()
                records.append(expected_row(blank_actual, {key: value for key, value in blank_values.items()
                                                            if key not in ("scoring_profile_id", "scoring_profile_version")},
                                            blank_profile, 2.0, None))
                require(blank_actual == records[-1], "all-blank profile score or null accuracy mismatch")

                legacy_values = payload("2026-11-11", "Mathematics", "Fractions", 12, 4, 4)
                legacy_actual = client.post("/practice", json=legacy_values).json()
                legacy_profile = {
                    "profile_id": "legacy-yks", "version": 1, "display_name": "YKS (legacy)",
                    "country_label": "Türkiye", "scoring_rule": {
                        "correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1",
                    },
                }
                records.append(expected_row(legacy_actual, legacy_values, legacy_profile, 11.0, 0.75))
                require(legacy_actual == records[-1], "legacy fallback score or full record mismatch")

                # Host-selected agent profile is included in the digest and saved snapshot; no provider route is mounted.
                agent_values = payload(TODAY, "Agent", "Host choice", 7, 2, 1, half_v1, minutes=18, seconds=0)
                agent_fields = {key: value for key, value in agent_values.items()
                                if key not in ("scoring_profile_id", "scoring_profile_version")}
                draft = client.post("/practice/agent-draft", json={
                    "messages": ["date: 2026-11-15, subject: Agent, topic: Host choice, correct: 7, incorrect: 2, blank: 1, duration_minutes: 18, duration_seconds: 0"],
                    "language": "en", "proposal": agent_fields,
                    "scoring_profile_id": half_v1["profile_id"], "scoring_profile_version": 1,
                })
                require(draft.status_code == 200 and draft.json()["preview_digest"], f"agent draft failed: {draft.text}")
                preview = draft.json()
                require(preview["scoring_profile_snapshot"] == half_v1 and preview["scoring_profile_version"] == 1,
                        "agent host choice was not resolved to the selected snapshot")
                approved = client.post("/practice/agent-create", json={
                    "messages": ["date: 2026-11-15, subject: Agent, topic: Host choice, correct: 7, incorrect: 2, blank: 1, duration_minutes: 18, duration_seconds: 0"],
                    "language": "en", "proposal": preview["proposal"], "fields": preview["fields"],
                    "evidence": preview["evidence"], "preview_digest": preview["preview_digest"],
                    "approval_id": str(uuid4()), "scoring_profile_id": half_v1["profile_id"],
                    "scoring_profile_version": 1, "scoring_profile_snapshot": half_v1,
                })
                agent_actual = approved.json()
                agent_row_values = {**agent_fields}
                records.append(expected_row(agent_actual, agent_row_values, half_v1, 6.25, 7 / 9))
                require(approved.status_code == 201 and agent_actual == records[-1], "agent-approved practice row differs from oracle")
                stale_snapshot = client.post("/practice/agent-create", json={
                    "messages": ["date: 2026-11-15, subject: Agent, topic: Host choice, correct: 7, incorrect: 2, blank: 1, duration_minutes: 18, duration_seconds: 0"],
                    "language": "en", "proposal": preview["proposal"], "fields": preview["fields"],
                    "evidence": preview["evidence"], "preview_digest": preview["preview_digest"],
                    "approval_id": str(uuid4()), "scoring_profile_id": half_v1["profile_id"],
                    "scoring_profile_version": 1, "scoring_profile_snapshot": half_v2,
                })
                require(stale_snapshot.status_code == 422, "agent create accepted a snapshot different from the host-selected version")

                # The focus timer stores v1. Carry 60 seconds from truncated milliseconds into minutes,
                # then prove completion retries preserve the exact selected snapshot and create once.
                completion_id = str(uuid4())
                elapsed_ms = 60_999
                elapsed_seconds = elapsed_ms // 1000
                duration_minutes, duration_seconds = elapsed_seconds // 60, elapsed_seconds % 60
                require((duration_minutes, duration_seconds) == (1, 0), "timer truncation/carry oracle changed")
                timer_draft = {
                    "date": "2026-11-10", "subject": "Mathematics", "topic": "Fractions",
                    "correct": 2, "incorrect": 1, "blank": 0, "completion_id": completion_id,
                    "scoring_profile": half_v1,
                }
                saved_timer = client.patch("/clock", json={"active_timer": {
                    "kind": "practice", "status": "paused", "elapsed_ms": elapsed_ms,
                    "practice_draft": timer_draft,
                }})
                require(saved_timer.status_code == 200 and
                        saved_timer.json()["active_timer"]["practice_draft"]["scoring_profile"] == half_v1,
                        "focus timer did not persist full scoring snapshot")
                focus_values = payload(timer_draft["date"], timer_draft["subject"], timer_draft["topic"],
                                       2, 1, 0, half_v1, duration_minutes, duration_seconds)
                first_focus = client.post("/practice", json=focus_values, headers={"Idempotency-Key": completion_id})
                focus_actual = first_focus.json()
                records.append(expected_row(focus_actual, {key: value for key, value in focus_values.items()
                                                           if key not in ("scoring_profile_id", "scoring_profile_version")},
                                            half_v1, 1.5, 2 / 3))
                require(first_focus.status_code == 201 and focus_actual == records[-1], "focus completion row or carried duration mismatch")
                replay = client.post("/practice", json=focus_values, headers={"Idempotency-Key": completion_id})
                require(replay.status_code == 201 and replay.json() == focus_actual, "same-key focus retry was not idempotent")
                altered_retry = client.post("/practice", json={**focus_values, "correct": 3}, headers={"Idempotency-Key": completion_id})
                require(altered_retry.status_code == 409, "same idempotency key accepted different practice content")

                persisted = client.get("/practice")
                require(persisted.status_code == 200 and persisted.json() == records,
                        "persisted practice list differs from complete independent full-row oracle")
                expected_groups = group_oracle(records)
                insights = client.get("/practice/insights")
                require(insights.status_code == 200 and insights.json() == expected_groups,
                        "profile/version-grouped topic summary differs from independent oracle")
                require({(row["scoring_profile"]["profile_id"], row["scoring_profile"]["version"])
                         for row in insights.json()} >= {
                             (half_v1["profile_id"], 1), (half_v1["profile_id"], 2),
                             (rational["profile_id"], 1), (blank_profile["profile_id"], 1), ("legacy-yks", 1),
                         }, "summary merged different profile versions")

                list_samples = []
                summary_samples = []
                for _ in range(repeats):
                    started = time.perf_counter()
                    current = client.get("/practice")
                    list_samples.append(time.perf_counter() - started)
                    require(current.status_code == 200 and current.json() == records,
                            "repeated persisted-list query changed complete rows")
                    started = time.perf_counter()
                    current = client.get("/practice/insights")
                    summary_samples.append(time.perf_counter() - started)
                    require(current.status_code == 200 and current.json() == expected_groups,
                            "repeated summary query changed profile partitions")

                with tempfile.TemporaryDirectory(prefix="hamartia-practice-backup-") as backup_root:
                    backup_path = Path(backup_root) / "current.zip"
                    restored_dir = Path(backup_root) / "current-restore"
                    create_backup(data_dir, backup_path)
                    restore_backup(backup_path, restored_dir)
                    restored_storage = StorageService(restored_dir)
                    restored_records = restored_storage.load_list("practice_sessions.json", PracticeSession)
                    require([item.model_dump(mode="json") for item in restored_records] == records,
                            "current backup restore changed full practice snapshots")
                    restored_profiles = restored_storage.load_list("exam_profiles.json", ExamScoringProfile)
                    expected_profiles = [half_v1, half_v2, rational, blank_profile]
                    require({(item.profile_id, item.version, item.model_dump(mode="json")["scoring_rule"]["correct_points"])
                             for item in restored_profiles} == {
                                 (item["profile_id"], item["version"], item["scoring_rule"]["correct_points"])
                                 for item in expected_profiles
                             },
                            "current backup restore changed the shared append-only profile catalog")
                    restored_clock = json.loads((restored_dir / "clock.json").read_text(encoding="utf-8"))
                    require(restored_clock["active_timer"]["practice_draft"]["scoring_profile"] == half_v1,
                            "current backup restore changed focus timer snapshot")

                    legacy_zip = Path(backup_root) / "legacy.zip"
                    legacy_restore = Path(backup_root) / "legacy-restore"
                    rewrite_as_legacy_archive(backup_path, legacy_zip)
                    restore_backup(legacy_zip, legacy_restore)
                    old_rows = StorageService(legacy_restore).load_list("practice_sessions.json", PracticeSession)
                    require(len(old_rows) == len(records) and all(row.scoring_profile.profile_id == "legacy-yks" for row in old_rows),
                            "legacy archive did not receive immutable legacy YKS snapshots")
                    require(old_rows[0].net == 9.0 and old_rows[3].accuracy is None,
                            "legacy archive fallback formula or all-blank accuracy changed")
                    old_profiles = StorageService(legacy_restore).load_list("exam_profiles.json", ExamScoringProfile)
                    require(old_profiles == [], "legacy archive unexpectedly restored a custom profile catalog")
                    old_clock = json.loads((legacy_restore / "clock.json").read_text(encoding="utf-8"))
                    require(old_clock["active_timer"]["practice_draft"]["scoring_profile"]["profile_id"] == "legacy-yks",
                            "legacy clock draft did not receive the safe profile default")

                return {
                    "benchmark": "versioned_practice_scoring_profiles",
                    "records": len(records), "profile_versions": len([half_v1, half_v2, rational, blank_profile]),
                    "group_count": len(expected_groups), "legacy_restore_rows": len(records),
                    "persisted_list_seconds": {
                        "p50": statistics.median(list_samples), "p95": percentile(list_samples, 0.95),
                    },
                    "summary_seconds": {
                        "p50": statistics.median(summary_samples), "p95": percentile(summary_samples, 0.95),
                    },
                    "correctness": "literal exact-rational scores, complete rows, profile-version groups, legacy/current backup round-trips and focus retry matched independent fixtures",
                    "timer_boundary": {"elapsed_ms": elapsed_ms, "duration_minutes": duration_minutes,
                                       "duration_seconds": duration_seconds, "same_key_retry": "same row; altered payload rejected"},
                    "ai_included": False,
                    "provider_calls": 0,
                    "network_access": False,
                }
        finally:
            for module, name, value in originals:
                setattr(module, name, value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    print(json.dumps(run(args.repeats), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
