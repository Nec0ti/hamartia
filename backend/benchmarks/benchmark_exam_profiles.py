"""Persisted/API benchmark for versioned exam scoring profiles; no AI/network calls."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import cosmos, exam_profiles, exams, user
from app.models.schemas import Exam, ExamScoringProfile, legacy_yks_profile
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService
from benchmark_common import emit, measure, probe_oracle_self_check


def main(repeats=7, json_output=None):
    if not 3 <= repeats <= 31:
        raise ValueError("repeats must be between 3 and 31")
    with tempfile.TemporaryDirectory(prefix="hamartia-exam-profile-bench-") as directory:
        storage = StorageService(Path(directory))
        app = FastAPI()
        app.include_router(exam_profiles.router)
        app.include_router(exams.router)
        app.include_router(user.router)
        app.include_router(cosmos.router)
        app.dependency_overrides[exam_profiles.get_storage] = lambda: storage
        app.dependency_overrides[exams.get_storage] = lambda: storage
        app.dependency_overrides[user.get_storage] = lambda: storage
        app.dependency_overrides[cosmos.get_storage] = lambda: storage
        client = TestClient(app)

        legacy = client.get("/exam-profiles").json()[0]
        assert legacy == _legacy_profile_vector()
        no_penalty = _create_profile(client, "SAT-like custom label", "Exampleland", "0/1")
        half_penalty = _create_profile(client, "LGS-like custom label", "Anotherland", "1/2")
        _assert_profile_vector(no_penalty, "SAT-like custom label", "Exampleland", "0/1")
        _assert_profile_vector(half_penalty, "LGS-like custom label", "Anotherland", "1/2")

        # Independent, hand-authored oracle for equal raw counts. These expected
        # values are deliberately literals, not calculations via production code.
        golden = {
            "legacy-yks@1": {"net": 11.0, "xp": 168},
            "custom-no-penalty@1": {"net": 12.0, "xp": 168},
            "custom-half-penalty@1": {"net": 10.0, "xp": 168},
        }
        expected_rows = []
        for profile_key, profile in (("legacy-yks@1", legacy),
                                      ("custom-no-penalty@1", no_penalty),
                                      ("custom-half-penalty@1", half_penalty)):
            payload = _exam_payload(profile)
            request_started = datetime.now(timezone.utc)
            response = client.post("/exams", json=payload)
            request_finished = datetime.now(timezone.utc)
            assert response.status_code == 201, response.text
            row = response.json()
            expected = _expected_response(payload, profile, golden[profile_key], row,
                                          request_started, request_finished)
            if row != expected:
                raise AssertionError(f"complete API response mismatch for {profile_key}: {row!r}")
            expected_rows.append(expected)

        # Persisted full mock verifies section totals and one aggregate score:
        # (4+8)/3 - (1+3)/6 + (1+3)/12 = 11/3.
        thirds = _create_profile(client, "Section thirds", "Exampleland", "1/6", correct="1/3", blank="1/12")
        _assert_profile_vector(thirds, "Section thirds", "Exampleland", "1/6",
                               correct="1/3", blank="1/12")
        mock_payload = _exam_payload(thirds, exam_type="tyt", sections=[
            {"subject": "Mathematics", "correct": 4, "incorrect": 1, "blank": 1},
            {"subject": "Language", "correct": 8, "incorrect": 3, "blank": 3},
        ])
        inconsistent_mock_input = {**mock_payload, "subject": "Wrong root subject",
                                   "correct": 900, "incorrect": 800, "blank": 700}
        request_started = datetime.now(timezone.utc)
        mock = client.post("/exams", json=inconsistent_mock_input)
        request_finished = datetime.now(timezone.utc)
        assert mock.status_code == 201, mock.text
        mock_row = mock.json()
        mock_expected = _expected_response(mock_payload, thirds, {"net": 11 / 3, "xp": 168}, mock_row,
                                           request_started, request_finished)
        if mock_row != mock_expected:
            raise AssertionError(f"complete sectioned API response mismatch: {mock_row!r}")
        expected_rows.append(mock_expected)

        # Editing a profile is append-only. v1 exam keeps its old saved rule;
        # new v2 record uses the new 1-point penalty and independently expected 8.
        revised = client.put(f"/exam-profiles/{no_penalty['profile_id']}", json={
            "display_name": "SAT-like custom label", "country_label": "Exampleland",
            "scoring_rule": {"correct_points": "1", "wrong_penalty": "1", "blank_points": "0"},
        })
        assert revised.status_code == 200 and revised.json()["version"] == 2
        catalog = client.get("/exam-profiles").json()
        no_penalty_v1 = next((item for item in catalog
                              if item["profile_id"] == no_penalty["profile_id"] and item["version"] == 1), None)
        no_penalty_v2 = next((item for item in catalog
                              if item["profile_id"] == no_penalty["profile_id"] and item["version"] == 2), None)
        assert no_penalty_v1 == no_penalty, "v1 must remain resolvable after v2 is appended"
        assert no_penalty_v2 == revised.json(), "catalog must expose appended v2 policy"
        _assert_profile_vector(revised.json(), "SAT-like custom label", "Exampleland", "1/1",
                               version=2)
        v2_payload = _exam_payload(revised.json())
        request_started = datetime.now(timezone.utc)
        v2 = client.post("/exams", json=v2_payload)
        request_finished = datetime.now(timezone.utc)
        assert v2.status_code == 201
        v2_expected = _expected_response(v2_payload, revised.json(), {"net": 8.0, "xp": 168}, v2.json(),
                                         request_started, request_finished)
        if v2.json() != v2_expected:
            raise AssertionError("complete v2 API response mismatch")
        expected_rows.append(v2_expected)

        # Blank-credit policy control: all-blank work may score positively, but
        # progression still follows raw correct/wrong counts and therefore stays 0.
        blank_credit = _create_profile(client, "Blank credit custom", "Exampleland",
                                       wrong="0/1", correct="1/1", blank="1/1")
        _assert_profile_vector(blank_credit, "Blank credit custom", "Exampleland", "0/1",
                               correct="1/1", blank="1/1")
        blank_payload = _exam_payload(blank_credit)
        blank_payload.update(subject="All blank", correct=0, incorrect=0, blank=4)
        request_started = datetime.now(timezone.utc)
        blank_response = client.post("/exams", json=blank_payload)
        request_finished = datetime.now(timezone.utc)
        assert blank_response.status_code == 201, blank_response.text
        blank_row = blank_response.json()
        blank_expected = _expected_response(blank_payload, blank_credit,
                                            {"net": 4.0, "xp": 0}, blank_row,
                                            request_started, request_finished)
        if blank_row != blank_expected:
            raise AssertionError("all-blank positive-score response must be net 4 / XP 0")
        expected_rows.append(blank_expected)

        fractional = _create_profile(client, "Prime denominator rule", "Exampleland",
                                     wrong="1/5", correct="1/3", blank="1/7")
        _assert_profile_vector(fractional, "Prime denominator rule", "Exampleland", "1/5",
                               correct="1/3", blank="1/7")
        created_profile_ids = [profile["profile_id"] for profile in
                               (no_penalty, half_penalty, thirds, blank_credit, fractional)]
        if len(created_profile_ids) != 5 or len(set(created_profile_ids)) != 5:
            raise AssertionError("each custom profile creation must return a distinct profile ID")
        fractional_payload = _exam_payload(fractional)
        fractional_payload.update(correct=2, incorrect=3, blank=4, duration_minutes=1)
        request_started = datetime.now(timezone.utc)
        fractional_response = client.post("/exams", json=fractional_payload)
        request_finished = datetime.now(timezone.utc)
        assert fractional_response.status_code == 201, fractional_response.text
        fractional_expected = _expected_response(
            fractional_payload, fractional, {"net": 67 / 105, "xp": 3}, fractional_response.json(),
            request_started, request_finished,
        )
        if fractional_response.json() != fractional_expected:
            raise AssertionError("relatively-prime denominators must score 67/105 and XP 3")
        expected_rows.append(fractional_expected)

        wrong_only_payload = _exam_payload(half_penalty)
        wrong_only_payload.update(correct=0, incorrect=5, blank=0)
        request_started = datetime.now(timezone.utc)
        wrong_only_response = client.post("/exams", json=wrong_only_payload)
        request_finished = datetime.now(timezone.utc)
        assert wrong_only_response.status_code == 201, wrong_only_response.text
        wrong_only_expected = _expected_response(
            wrong_only_payload, half_penalty, {"net": -2.5, "xp": 0}, wrong_only_response.json(),
            request_started, request_finished,
        )
        if wrong_only_response.json() != wrong_only_expected:
            raise AssertionError("wrong-only split must retain negative custom net and zero XP")
        expected_rows.append(wrong_only_expected)

        zero_payload = _exam_payload(legacy)
        zero_payload.update(correct=0, incorrect=0, blank=0)
        request_started = datetime.now(timezone.utc)
        zero_response = client.post("/exams", json=zero_payload)
        request_finished = datetime.now(timezone.utc)
        assert zero_response.status_code == 201, zero_response.text
        zero_expected = _expected_response(
            zero_payload, legacy, {"net": 0.0, "xp": 0}, zero_response.json(),
            request_started, request_finished,
        )
        if zero_response.json() != zero_expected:
            raise AssertionError("zero-question exam must remain net 0 / XP 0")
        expected_rows.append(zero_expected)

        rows = client.get("/exams").json()
        if rows != expected_rows:
            raise AssertionError("persisted GET /exams did not preserve complete expected records")
        post_ids = [row["id"] for row in rows]
        if len(post_ids) != 9 or len(set(post_ids)) != 9:
            raise AssertionError("each of the nine POST /exams requests must persist a distinct valid ID")
        user_stats = client.get("/user").json()
        cosmos_state = client.get("/cosmos").json()
        if user_stats["total_xp"] != 843 or user_stats["level"] != 2 or cosmos_state["user_xp"] != 843:
            raise AssertionError("global user/Cosmos progression must use the same raw-count XP across profiles")
        by_key = {}
        for row in rows:
            profile = row["scoring_profile"]
            by_key.setdefault(f"{profile['profile_id']}@{profile['version']}", []).append(row)
        actual = {
            "legacy-yks@1": by_key["legacy-yks@1"],
            f"{no_penalty['profile_id']}@1": by_key[f"{no_penalty['profile_id']}@1"],
            f"{no_penalty['profile_id']}@2": by_key[f"{no_penalty['profile_id']}@2"],
            f"{half_penalty['profile_id']}@1": by_key[f"{half_penalty['profile_id']}@1"],
            f"{thirds['profile_id']}@1": by_key[f"{thirds['profile_id']}@1"],
            f"{blank_credit['profile_id']}@1": by_key[f"{blank_credit['profile_id']}@1"],
            f"{fractional['profile_id']}@1": by_key[f"{fractional['profile_id']}@1"],
        }
        expected = {
            "legacy-yks@1": [expected_rows[0], expected_rows[8]],
            f"{no_penalty['profile_id']}@1": [expected_rows[1]],
            f"{no_penalty['profile_id']}@2": [expected_rows[4]],
            f"{half_penalty['profile_id']}@1": [expected_rows[2], expected_rows[7]],
            f"{thirds['profile_id']}@1": [expected_rows[3]],
            f"{blank_credit['profile_id']}@1": [expected_rows[5]],
            f"{fractional['profile_id']}@1": [expected_rows[6]],
        }
        for key, full_rows in actual.items():
            if full_rows != expected[key]:
                raise AssertionError(f"persisted profile isolation mismatch at {key}: {full_rows!r}")
        # Sensitivity control: same profile/request row with only a derived score
        # corrupted must be rejected by the full-vector comparison.
        corrupted = json.loads(json.dumps(actual))
        corrupted[f"{half_penalty['profile_id']}@1"][0]["net"] += 0.25
        assert corrupted != expected
        assert probe_oracle_self_check(
            actual, expected,
            lambda rows: rows[f"{half_penalty['profile_id']}@1"][0].__setitem__("net", 10.25),
            "half-penalty net corrupted by 0.25",
        ) == "half-penalty net corrupted by 0.25"

        reloaded = StorageService(Path(directory)).load_list("exams.json", Exam)
        if len(reloaded) != 9:
            raise AssertionError("persisted record count mismatch")
        # Old pre-profile JSON has no snapshot field and must still score as
        # legacy YKS. The same persisted profile and exam versions must survive
        # a real ZIP backup/restore round trip.
        old_dir = Path(directory) / "legacy-fixture"
        old_dir.mkdir()
        (old_dir / "exams.json").write_text(json.dumps([{
            "id": "legacy-before-profile", "date": "2025-01-02", "exam_type": "branch",
            "subject": "Mathematics", "correct": 12, "incorrect": 4, "blank": 4,
            "duration_minutes": 30, "duration_seconds": 0, "created_at": "2025-01-02T00:00:00Z",
        }]), encoding="utf-8")
        legacy_loaded = StorageService(old_dir).load_list("exams.json", Exam)[0]
        if legacy_loaded.scoring_profile != legacy_yks_profile() or legacy_loaded.net != 11.0:
            raise AssertionError("legacy JSON did not default to legacy-yks@1 with net 11")
        old_backup = Path(directory).parent / f"{Path(directory).name}-old-backup.zip"
        pre_profile_zip = Path(directory).parent / f"{Path(directory).name}-pre-profile.zip"
        legacy_restore = Path(directory) / "legacy-backup-restore"
        try:
            create_backup(old_dir, old_backup)
            with zipfile.ZipFile(old_backup) as source_archive:
                members = {name: source_archive.read(name) for name in source_archive.namelist()}
            members.pop("exam_profiles.json", None)
            old_rows = json.loads(members["exams.json"])
            for record in old_rows:
                record.pop("scoring_profile", None)
            old_exam_bytes = json.dumps(old_rows, ensure_ascii=False, separators=(",", ":")).encode()
            members["exams.json"] = old_exam_bytes
            manifest = json.loads(members["manifest.json"])
            manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != "exam_profiles.json"]
            exam_entry = next(entry for entry in manifest["files"] if entry["path"] == "exams.json")
            exam_entry.update(size=len(old_exam_bytes), sha256=hashlib.sha256(old_exam_bytes).hexdigest())
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode()
            with zipfile.ZipFile(pre_profile_zip, "w", compression=zipfile.ZIP_DEFLATED) as old_format_archive:
                for name, content in members.items():
                    if name != "manifest.json":
                        old_format_archive.writestr(name, content)
                old_format_archive.writestr("manifest.json", manifest_bytes)
            restore_backup(pre_profile_zip, legacy_restore)
            legacy_zip_exam = StorageService(legacy_restore).load_list("exams.json", Exam)[0]
            legacy_zip_profiles = StorageService(legacy_restore).load_list("exam_profiles.json", ExamScoringProfile)
            if legacy_zip_exam.scoring_profile != legacy_yks_profile() or legacy_zip_exam.net != 11.0 or legacy_zip_profiles:
                raise AssertionError("pre-profile ZIP without catalog did not restore legacy YKS net 11")
        finally:
            old_backup.unlink(missing_ok=True)
            pre_profile_zip.unlink(missing_ok=True)
        backup_path = Path(directory).parent / f"{Path(directory).name}-profile-backup.zip"
        restored_dir = Path(directory) / "restored-data"
        try:
            create_backup(Path(directory), backup_path)
            restore_backup(backup_path, restored_dir)
            restored_storage = StorageService(restored_dir)
            restored = restored_storage.load_list("exams.json", Exam)
            restored_custom = restored_storage.load_list("exam_profiles.json", ExamScoringProfile)
            restored_rows = [row.model_dump(mode="json") for row in restored]
            expected_custom_profiles = [no_penalty, half_penalty, thirds, revised.json(), blank_credit, fractional]
            restored_profiles = [profile.model_dump(mode="json") for profile in restored_custom]
            if restored_rows != expected_rows:
                raise AssertionError("backup restore changed or lost any complete exam snapshot")
            if restored_profiles != expected_custom_profiles:
                raise AssertionError("backup restore changed or lost any complete custom profile version")
        finally:
            backup_path.unlink(missing_ok=True)
        serialized_bytes = (Path(directory) / "exams.json").stat().st_size
        def list_api():
            response = client.get("/exams")
            if response.status_code != 200 or response.json() != expected_rows:
                raise AssertionError("timed API read differed from complete persisted-record oracle")

        report = {
            "benchmark": "versioned_exam_scoring_profiles",
            "ai_included": False,
            "network": "in-process FastAPI TestClient only; no external or provider calls",
            "persisted_records": len(reloaded),
            "persisted_exam_bytes": serialized_bytes,
            "profile_versions": 7,
            "raw_counts_per_golden": {"correct": 12, "incorrect": 4, "blank": 4},
            "hand_authored_goldens": golden,
            "all_blank_positive_score": {"rule": [1, 0, 1], "correct": 0, "incorrect": 0, "blank": 4, "net": 4.0, "xp": 0},
            "relatively_prime_denominators": {"rule": ["1/3", "1/5", "1/7"], "counts": [2, 3, 4], "net": "67/105", "xp": 3},
            "wrong_only_and_zero_question": [{"counts": [0, 5, 0], "net": -2.5, "xp": 0}, {"counts": [0, 0, 0], "net": 0.0, "xp": 0}],
            "section_total_golden": {"counts": [12, 4, 4], "net": 11 / 3},
            "section_root_total_control": "API ignored deliberately mismatched root counts/subject and persisted the exact two section records",
            "legacy_and_custom_xp_equal": [168, 168, 168],
            "global_progression": {"raw_count_xp_total": 843, "user_level": 2, "cosmos_user_xp": 843},
            "legacy_json_migration": {"missing_snapshot_defaults_to": "legacy-yks@1", "net": legacy_loaded.net},
            "legacy_zip_migration": "pre-profile archive without exam_profiles.json restored legacy-yks@1 with net 11",
            "backup_restore": "all nine complete exam rows and six complete custom profile versions matched independent vectors",
            "oracle": "complete persisted API rows including counts, exact section names, XP, snapshots, and metadata, partitioned by profile ID/version; literal score goldens",
            "negative_control": "same request/profile with net changed by 0.25 changes expected full-state vector",
            "api_list_timing": measure(list_api, repeats),
        }
        emit(report, json_output)


def _create_profile(client, display_name, country_label, wrong, correct="1/1", blank="0/1"):
    response = client.post("/exam-profiles", json={
        "display_name": display_name, "country_label": country_label,
        "scoring_rule": {"correct_points": correct, "wrong_penalty": wrong, "blank_points": blank},
    })
    if response.status_code != 201:
        raise AssertionError(response.text)
    return response.json()


def _legacy_profile_vector():
    return {
        "profile_id": "legacy-yks", "version": 1,
        "display_name": "YKS (legacy)", "country_label": "Türkiye",
        "scoring_rule": {"correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1"},
    }


def _assert_profile_vector(profile, display_name, country_label, wrong_penalty,
                            correct="1/1", blank="0/1", version=1):
    assert profile["profile_id"].startswith("profile_") and len(profile["profile_id"]) == 40
    UUID(hex=profile["profile_id"][8:])
    expected = {
        "profile_id": profile["profile_id"], "version": version,
        "display_name": display_name, "country_label": country_label,
        "scoring_rule": {
            "correct_points": correct, "wrong_penalty": wrong_penalty, "blank_points": blank,
        },
    }
    assert profile == expected


def _expected_response(payload, profile, golden, actual, started_at, finished_at):
    """Complete route oracle with dynamic ID/time checked for shape separately."""
    exam_id = actual.get("id", "")
    assert exam_id.startswith("exam_") and len(exam_id) == 37
    UUID(hex=exam_id[5:])
    created_at = actual.get("created_at", "")
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert started_at.replace(microsecond=0) <= created <= finished_at.replace(microsecond=0)
    if profile["profile_id"] == "legacy-yks":
        snapshot = _legacy_profile_vector()
    else:
        snapshot = {
            "profile_id": profile["profile_id"], "version": profile["version"],
            "display_name": profile["display_name"], "country_label": profile["country_label"],
            "scoring_rule": dict(profile["scoring_rule"]),
        }
    expected = {key: value for key, value in payload.items()
                if key not in ("scoring_profile_id", "scoring_profile_version")}
    expected.update({
        "id": exam_id, "created_at": created_at,
        "total": payload["correct"] + payload["incorrect"],
        "net": golden["net"], "xp": golden["xp"], "scoring_profile": snapshot,
    })
    return expected


def _exam_payload(profile, exam_type="branch", sections=None):
    if sections:
        correct = sum(item["correct"] for item in sections)
        incorrect = sum(item["incorrect"] for item in sections)
        blank = sum(item["blank"] for item in sections)
        subject = f"{exam_type.upper()} Geneli"
    else:
        correct, incorrect, blank, subject = 12, 4, 4, "Custom profile benchmark"
    return {
        "date": "2026-11-15", "exam_type": exam_type, "subject": subject,
        "correct": correct, "incorrect": incorrect, "blank": blank,
        "duration_minutes": 30, "duration_seconds": 0, "sections": sections or [],
        "scoring_profile_id": profile["profile_id"],
        "scoring_profile_version": profile["version"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
