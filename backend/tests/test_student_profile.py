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
        self.assertEqual(self.client.get("/student-profile").json(), profile)
        self.assertEqual(json.loads((self.data_dir / "onboarding.json").read_text()), profile)
        profile["profile"]["nickname"] = "Updated nickname"
        self.assertEqual(self.client.put("/student-profile", json=profile).json(), profile)
        self.assertEqual(self.client.delete("/student-profile").json(), empty)
        self.assertEqual(self.client.get("/student-profile").json(), empty)

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

    def test_competing_full_document_updates_do_not_produce_malformed_json(self):
        profiles = [
            {"survey_completed": True, "profile": {"nickname": f"student-{i}", "age_years": 16}}
            for i in range(16)
        ]
        def save(value):
            response = self.client.put("/student-profile", json=value)
            self.assertEqual(response.status_code, 200)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(save, profiles))
        stored = json.loads((self.data_dir / "onboarding.json").read_text())
        self.assertIn(stored["profile"]["nickname"], {row["profile"]["nickname"] for row in profiles})
        self.assertEqual(self.client.get("/student-profile").json(), stored)

    def test_backup_round_trip_and_legacy_backup_default_empty(self):
        value = StudentOnboarding(
            survey_completed=True,
            profile={"nickname": "Synthetic", "age_years": 17, "curriculum": "Custom", "avatar_preset": "book"},
        )
        (self.data_dir / "onboarding.json").write_text(value.model_dump_json(), encoding="utf-8")
        archive = Path(self.temp.name) / "profile.zip"
        backup.create_backup(self.data_dir, archive)
        restored = Path(self.temp.name) / "restored"
        backup.extract_backup(archive, restored)
        self.assertEqual(json.loads((restored / "onboarding.json").read_text()), value.model_dump(mode="json"))

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
