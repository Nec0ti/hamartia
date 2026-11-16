import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import exam_profiles, practice
from app.models.schemas import ExamScoringProfile, PracticeSession, PracticeSessionCreate
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService


class PracticeScoringProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name) / "data"
        self.data_dir.mkdir()
        self.storage = StorageService(self.data_dir)
        self.practice_data = patch.object(practice, "DATA_DIR", self.data_dir)
        self.profile_data = patch.object(exam_profiles, "DATA_DIR", self.data_dir)
        self.practice_data.start()
        self.profile_data.start()
        app = FastAPI()
        app.include_router(exam_profiles.router)
        app.include_router(practice.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.practice_data.stop()
        self.profile_data.stop()
        self.temp.cleanup()

    def payload(self, **values):
        return {
            "date": "2026-11-15", "subject": "Mathematics", "topic": "Fractions",
            "correct": 2, "incorrect": 1, "blank": 4, "duration_minutes": 12,
            **values,
        }

    def create_profile(self, name="Fractional", correct="1/3", penalty="1/6", blank="1/12"):
        response = self.client.post("/exam-profiles", json={
            "display_name": name, "country_label": "Example",
            "scoring_rule": {"correct_points": correct, "wrong_penalty": penalty, "blank_points": blank},
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_legacy_custom_exact_fraction_versions_editing_and_partitioned_summary(self):
        legacy_file = self.data_dir / "practice_sessions.json"
        legacy_file.write_text(json.dumps([{
            "id": "legacy", "date": "2026-11-14", "subject": "Mathematics", "topic": "Fractions",
            "correct": 2, "incorrect": 1, "blank": 0,
        }]), encoding="utf-8")
        legacy = self.client.get("/practice").json()[0]
        self.assertEqual((legacy["scoring_profile"]["profile_id"], legacy["net"], legacy["accuracy"]),
                         ("legacy-yks", 1.75, 2 / 3))

        version_one = self.create_profile()
        first = self.client.post("/practice", json=self.payload(
            scoring_profile_id=version_one["profile_id"], scoring_profile_version=1,
        ))
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["net"], 5 / 6)
        self.assertEqual(first.json()["accuracy"], 2 / 3)

        version_two = self.client.put(f"/exam-profiles/{version_one['profile_id']}", json={
            "display_name": "No penalty", "country_label": "Example",
            "scoring_rule": {"correct_points": "1", "wrong_penalty": "0", "blank_points": "0"},
        })
        self.assertEqual(version_two.json()["version"], 2)

        omitted = self.client.put(f"/practice/{first.json()['id']}", json=self.payload(correct=3))
        self.assertEqual((omitted.json()["scoring_profile"]["version"], omitted.json()["net"]), (1, 7 / 6))
        explicitly_selected = self.client.put(f"/practice/{first.json()['id']}", json=self.payload(
            correct=3, scoring_profile_id=version_two.json()["profile_id"], scoring_profile_version=2,
        ))
        self.assertEqual((explicitly_selected.json()["scoring_profile"]["version"], explicitly_selected.json()["net"]), (2, 3))

        summaries = self.client.get("/practice/insights").json()
        self.assertEqual({(row["scoring_profile"]["profile_id"], row["scoring_profile"]["version"]) for row in summaries}, {
            ("legacy-yks", 1), (version_one["profile_id"], 2),
        })

    def test_validation_all_blank_and_current_backup_round_trip(self):
        for values in ({"correct": -1}, {"correct": 0, "incorrect": 0, "blank": 0}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                PracticeSessionCreate(**self.payload(**values))

        blank_profile = self.create_profile("Blank credit", correct="0", penalty="0", blank="1/2")
        blank = self.client.post("/practice", json=self.payload(
            correct=0, incorrect=0, blank=4,
            scoring_profile_id=blank_profile["profile_id"], scoring_profile_version=1,
        ))
        self.assertEqual((blank.json()["net"], blank.json()["accuracy"]), (2, None))
        (self.data_dir / "practice_sessions.json").write_text(json.dumps([{
            "id": "legacy", "date": "2026-11-14", "subject": "Mathematics", "topic": "Fractions",
            "correct": 2, "incorrect": 1, "blank": 0,
        }, blank.json()]), encoding="utf-8")

        archive = Path(self.temp.name) / "current.zip"
        restored_dir = Path(self.temp.name) / "restored"
        create_backup(self.data_dir, archive)
        restore_backup(archive, restored_dir)
        restored_storage = StorageService(restored_dir)
        restored = restored_storage.load_list("practice_sessions.json", PracticeSession)
        self.assertEqual([(item.id, item.scoring_profile.profile_id, item.net) for item in restored], [
            ("legacy", "legacy-yks", 1.75), (blank.json()["id"], blank_profile["profile_id"], 2.0),
        ])
        self.assertEqual([item.version for item in restored_storage.load_list("exam_profiles.json", ExamScoringProfile)], [1])


if __name__ == "__main__":
    unittest.main()
