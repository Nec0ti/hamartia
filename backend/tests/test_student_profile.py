"""Local-only student profile persistence and backup compatibility."""

import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import student_profile
from app.models.schemas import StudentOnboarding
from app.services import backup


def make_app():
    app = FastAPI()
    app.include_router(student_profile.router)
    return app


class StudentProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name) / "data"
        self.data_dir.mkdir()
        self.patch = patch.object(student_profile, "DATA_DIR", self.data_dir)
        self.patch.start()
        self.client = TestClient(make_app())

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.temp.cleanup()

    def test_missing_profile_is_empty_and_save_edit_reset_are_local(self):
        empty = StudentOnboarding().model_dump(mode="json")
        self.assertEqual(self.client.get("/student-profile").json(), empty)
        profile = {
            "tutorial_completed": True,
            "tutorial_skipped": False,
            "survey_completed": True,
            "profile": {
                "nickname": "Study buddy", "age_years": 17, "grade_year": "11",
                "curriculum": "Custom / Türkiye", "study_preferences": "Short sessions",
                "study_goals": "Practice algebra", "avatar_preset": "moon",
            },
        }
        saved = self.client.put("/student-profile", json=profile)
        self.assertEqual(saved.status_code, 200, saved.text)
        expected = {**profile, "revision": 1}
        self.assertEqual(saved.json(), expected)
        self.assertEqual(self.client.get("/student-profile").json(), expected)
        self.assertEqual(json.loads((self.data_dir / "onboarding.json").read_text()), expected)
        profile["profile"]["nickname"] = "Updated nickname"
        profile["revision"] = expected["revision"]
        edited = {**profile, "revision": 2}
        self.assertEqual(self.client.put("/student-profile", json=profile).json(), edited)
        reset = {**empty, "revision": 3}
        self.assertEqual(self.client.delete("/student-profile").json(), reset)
        self.assertEqual(self.client.get("/student-profile").json(), reset)

    def test_validation_rejects_birth_date_gender_unknown_fields_and_bad_values(self):
        base = StudentOnboarding().model_dump(mode="json")
        for field, value in (("birth_date", "2009-01-02"), ("gender", "unspecified")):
            invalid = {**base, "profile": {**base["profile"], field: value}}
            self.assertEqual(self.client.put("/student-profile", json=invalid).status_code, 422)
        for age in (True, 4, 121, "17"):
            invalid = {**base, "profile": {**base["profile"], "age_years": age}}
            self.assertEqual(self.client.put("/student-profile", json=invalid).status_code, 422)
        invalid_avatar = {**base, "profile": {**base["profile"], "avatar_preset": "remote-url"}}
        self.assertEqual(self.client.put("/student-profile", json=invalid_avatar).status_code, 422)

    def test_avatar_unlocks_use_existing_level_boundaries_and_cannot_be_forged(self):
        for preset, threshold in (("comet", 500), ("planet", 1000), ("galaxy", 2000)):
            original = self.client.get("/student-profile").json()
            original["profile"]["avatar_preset"] = preset
            (self.data_dir / "user.json").write_text(json.dumps({"total_xp": threshold - 1}), encoding="utf-8")
            self.assertEqual(self.client.put("/student-profile", json=original).status_code, 422)
            (self.data_dir / "user.json").write_text(json.dumps({"total_xp": threshold}), encoding="utf-8")
            saved = self.client.put("/student-profile", json=original)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()["profile"]["avatar_preset"], preset)

        free = self.client.get("/student-profile").json()
        free["profile"]["avatar_preset"] = "sunrise"
        (self.data_dir / "user.json").write_text(json.dumps({"total_xp": 0}), encoding="utf-8")
        self.assertEqual(self.client.put("/student-profile", json=free).status_code, 200)

    def test_malformed_saved_profile_fails_closed_without_overwrite(self):
        raw = '{"profile":'
        path = self.data_dir / "onboarding.json"
        path.write_text(raw, encoding="utf-8")
        with TestClient(make_app(), raise_server_exceptions=False) as client:
            self.assertEqual(client.get("/student-profile").status_code, 500)
        self.assertEqual(path.read_text(encoding="utf-8"), raw)

    def test_stale_write_fails_and_competing_full_document_updates_keep_one_exact_row(self):
        original = self.client.get("/student-profile").json()
        first = {**original, "survey_completed": True, "profile": {"nickname": "First writer", "age_years": 16}}
        accepted = self.client.put("/student-profile", json=first)
        self.assertEqual(accepted.status_code, 200)
        stale = {**original, "survey_completed": True, "profile": {"nickname": "Stale writer", "age_years": 17}}
        self.assertEqual(self.client.put("/student-profile", json=stale).status_code, 409)
        self.assertEqual(self.client.get("/student-profile").json(), accepted.json())
        profiles = [
            {"revision": accepted.json()["revision"], "survey_completed": True, "profile": {"nickname": f"student-{i}", "age_years": 16}}
            for i in range(16)
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda value: self.client.put("/student-profile", json=value), profiles))
        self.assertEqual(sum(response.status_code == 200 for response in responses), 1)
        self.assertEqual(sum(response.status_code == 409 for response in responses), len(profiles) - 1)
        stored = json.loads((self.data_dir / "onboarding.json").read_text())
        self.assertIn(stored["profile"]["nickname"], {row["profile"]["nickname"] for row in profiles})
        self.assertEqual(self.client.get("/student-profile").json(), stored)

    def test_backup_round_trip_and_legacy_backup_default_empty(self):
        for preset in ("book", "comet", "planet", "galaxy"):
            value = StudentOnboarding(
                survey_completed=True,
                profile={"nickname": "Synthetic", "age_years": 17, "curriculum": "Custom", "avatar_preset": preset},
            )
            (self.data_dir / "onboarding.json").write_text(value.model_dump_json(), encoding="utf-8")
            archive = Path(self.temp.name) / f"profile-{preset}.zip"
            backup.create_backup(self.data_dir, archive)
            restored = Path(self.temp.name) / f"restored-{preset}"
            backup.extract_backup(archive, restored)
            self.assertEqual(json.loads((restored / "onboarding.json").read_text()), value.model_dump(mode="json"))

        invalid_archive = Path(self.temp.name) / "unknown-avatar.zip"
        with backup.zipfile.ZipFile(archive) as source, backup.zipfile.ZipFile(invalid_archive, "w") as target:
            manifest = json.loads(source.read("manifest.json"))
            for entry in manifest["files"]:
                raw = source.read(entry["path"])
                if entry["path"] == "onboarding.json":
                    value = json.loads(raw)
                    value["profile"]["avatar_preset"] = "remote-avatar"
                    raw = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
                    entry["size"] = len(raw)
                    entry["sha256"] = hashlib.sha256(raw).hexdigest()
                target.writestr(entry["path"], raw)
            target.writestr("manifest.json", json.dumps(manifest))
        with self.assertRaises(backup.BackupError):
            backup.extract_backup(invalid_archive, Path(self.temp.name) / "invalid-restored")

        legacy_path = Path(self.temp.name) / "legacy-v1.zip"
        with backup.zipfile.ZipFile(archive) as current, backup.zipfile.ZipFile(legacy_path, "w") as old:
            names = [name for name in current.namelist() if name not in ("manifest.json", "onboarding.json")]
            entries = []
            for name in names:
                raw = current.read(name)
                old.writestr(name, raw)
                entries.append({"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            old.writestr("manifest.json", json.dumps({
                "format": backup.BACKUP_FORMAT, "version": backup.BACKUP_VERSION, "files": entries,
            }))
        legacy_restored = Path(self.temp.name) / "legacy-restored"
        backup.extract_backup(legacy_path, legacy_restored)
        self.assertEqual(json.loads((legacy_restored / "onboarding.json").read_text()), StudentOnboarding().model_dump(mode="json"))
