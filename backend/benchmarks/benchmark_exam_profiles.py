"""Persisted/API benchmark for versioned exam scoring profiles; no AI/network calls."""

import argparse
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import exam_profiles, exams
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
        app.dependency_overrides[exam_profiles.get_storage] = lambda: storage
        app.dependency_overrides[exams.get_storage] = lambda: storage
        client = TestClient(app)

        legacy = client.get("/exam-profiles").json()[0]
        assert legacy["profile_id"] == "legacy-yks" and legacy["version"] == 1
        no_penalty = _create_profile(client, "SAT-like custom label", "Exampleland", "0/1")
        half_penalty = _create_profile(client, "LGS-like custom label", "Anotherland", "1/2")

        # Independent, hand-authored oracle for equal raw counts. These expected
        # values are deliberately literals, not calculations via production code.
        golden = {
            "legacy-yks@1": {"net": 11.0, "xp": 168},
            f"{no_penalty['profile_id']}@1": {"net": 12.0, "xp": 168},
            f"{half_penalty['profile_id']}@1": {"net": 10.0, "xp": 168},
        }
        for profile_key, profile in (("legacy-yks@1", legacy),
                                      (f"{no_penalty['profile_id']}@1", no_penalty),
                                      (f"{half_penalty['profile_id']}@1", half_penalty)):
            response = client.post("/exams", json=_exam_payload(profile))
            assert response.status_code == 201, response.text
            row = response.json()
            assert row["net"] == golden[profile_key]["net"]
            assert row["xp"] == golden[profile_key]["xp"]
            assert row["scoring_profile"]["profile_id"] == profile["profile_id"]
            assert row["scoring_profile"]["version"] == 1

        # Persisted full mock verifies section totals and one aggregate score:
        # (4+8)/3 - (1+3)/6 + (1+3)/12 = 11/3.
        thirds = _create_profile(client, "Section thirds", "Exampleland", "1/6", correct="1/3", blank="1/12")
        mock_payload = _exam_payload(thirds, exam_type="tyt", sections=[
            {"subject": "Mathematics", "correct": 4, "incorrect": 1, "blank": 1},
            {"subject": "Language", "correct": 8, "incorrect": 3, "blank": 3},
        ])
        mock = client.post("/exams", json=mock_payload)
        assert mock.status_code == 201, mock.text
        mock_row = mock.json()
        assert (mock_row["correct"], mock_row["incorrect"], mock_row["blank"]) == (12, 4, 4)
        assert mock_row["net"] == 11 / 3
        assert len(mock_row["sections"]) == 2

        # Editing a profile is append-only. v1 exam keeps its old saved rule;
        # new v2 record uses the new 1-point penalty and independently expected 8.
        revised = client.put(f"/exam-profiles/{no_penalty['profile_id']}", json={
            "display_name": "SAT-like custom label", "country_label": "Exampleland",
            "scoring_rule": {"correct_points": "1", "wrong_penalty": "1", "blank_points": "0"},
        })
        assert revised.status_code == 200 and revised.json()["version"] == 2
        v2_payload = _exam_payload(revised.json())
        v2 = client.post("/exams", json=v2_payload)
        assert v2.status_code == 201 and v2.json()["net"] == 8.0

        rows = client.get("/exams").json()
        by_key = {}
        for row in rows:
            profile = row["scoring_profile"]
            by_key.setdefault(f"{profile['profile_id']}@{profile['version']}", []).append(row)
        actual = {
            "legacy-yks@1": [row["net"] for row in by_key["legacy-yks@1"]],
            f"{no_penalty['profile_id']}@1": [row["net"] for row in by_key[f"{no_penalty['profile_id']}@1"]],
            f"{no_penalty['profile_id']}@2": [row["net"] for row in by_key[f"{no_penalty['profile_id']}@2"]],
            f"{half_penalty['profile_id']}@1": [row["net"] for row in by_key[f"{half_penalty['profile_id']}@1"]],
            f"{thirds['profile_id']}@1": [row["net"] for row in by_key[f"{thirds['profile_id']}@1"]],
        }
        expected = {
            "legacy-yks@1": [11.0],
            f"{no_penalty['profile_id']}@1": [12.0],
            f"{no_penalty['profile_id']}@2": [8.0],
            f"{half_penalty['profile_id']}@1": [10.0],
            f"{thirds['profile_id']}@1": [11 / 3],
        }
        if actual != expected:
            raise AssertionError(f"persisted profile isolation mismatch: {actual!r}")
        # Sensitivity control: same profile/request row with only a derived score
        # corrupted must be rejected by the full-vector comparison.
        corrupted = {key: list(values) for key, values in actual.items()}
        corrupted[f"{half_penalty['profile_id']}@1"][0] += 0.25
        assert corrupted != expected
        assert probe_oracle_self_check(
            actual, expected,
            lambda rows: rows[f"{half_penalty['profile_id']}@1"].__setitem__(0, 10.25),
            "half-penalty net corrupted by 0.25",
        ) == "half-penalty net corrupted by 0.25"

        reloaded = StorageService(Path(directory)).load_list("exams.json", Exam)
        if len(reloaded) != 5:
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
        backup_path = Path(directory).parent / f"{Path(directory).name}-profile-backup.zip"
        restored_dir = Path(directory) / "restored-data"
        try:
            create_backup(Path(directory), backup_path)
            restore_backup(backup_path, restored_dir)
            restored = StorageService(restored_dir).load_list("exams.json", Exam)
            restored_custom = StorageService(restored_dir).load_list("exam_profiles.json", ExamScoringProfile)
            if len(restored) != 5 or len(restored_custom) != 4:
                raise AssertionError("backup restore lost exam/profile versions")
            if next(row for row in restored if row.scoring_profile.profile_id == no_penalty["profile_id"] and row.scoring_profile.version == 1).net != 12.0:
                raise AssertionError("backup restore changed old profile snapshot score")
        finally:
            backup_path.unlink(missing_ok=True)
        serialized_bytes = (Path(directory) / "exams.json").stat().st_size
        def list_api():
            response = client.get("/exams")
            if response.status_code != 200 or len(response.json()) != 5:
                raise AssertionError("timed API read returned incomplete records")

        report = {
            "benchmark": "versioned_exam_scoring_profiles",
            "ai_included": False,
            "network": "in-process FastAPI TestClient only; no external or provider calls",
            "persisted_records": len(reloaded),
            "persisted_exam_bytes": serialized_bytes,
            "profile_versions": 5,
            "raw_counts_per_golden": {"correct": 12, "incorrect": 4, "blank": 4},
            "hand_authored_goldens": golden,
            "section_total_golden": {"counts": [12, 4, 4], "net": 11 / 3},
            "legacy_and_custom_xp_equal": [168, 168, 168],
            "legacy_json_migration": {"missing_snapshot_defaults_to": "legacy-yks@1", "net": legacy_loaded.net},
            "backup_restore": "all five exam snapshots and four custom profile versions preserved",
            "oracle": "full persisted API responses partitioned by exact profile ID and version; literal score goldens",
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
