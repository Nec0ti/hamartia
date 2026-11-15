import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.exam_profiles import create_profile, update_profile
from app.api.exams import create_exam, update_exam
from app.models.schemas import Exam, ExamCreate, ExamScoringProfile, ExamScoringProfileCreate, ExamScoringRule
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService


def payload(profile_id=None, version=None, **counts):
    return ExamCreate(
        date="2026-11-15", exam_type="branch", subject="Synthetic",
        correct=counts.get("correct", 12), incorrect=counts.get("incorrect", 4), blank=counts.get("blank", 4),
        duration_minutes=30, scoring_profile_id=profile_id, scoring_profile_version=version,
    )


class ExamScoringProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = StorageService(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_profile(self, display_name, correct="1", penalty="0", blank="0"):
        return asyncio.run(create_profile(ExamScoringProfileCreate(
            display_name=display_name, country_label="Example", scoring_rule=ExamScoringRule(
                correct_points=correct, wrong_penalty=penalty, blank_points=blank,
            ),
        ), self.storage))

    def test_hand_authored_golden_scores_and_profile_independent_xp(self):
        no_penalty = self.create_profile("No penalty")
        half_penalty = self.create_profile("Half penalty", penalty="1/2")
        exams = [
            asyncio.run(create_exam(payload(), self.storage)),
            asyncio.run(create_exam(payload(no_penalty.profile_id, no_penalty.version), self.storage)),
            asyncio.run(create_exam(payload(half_penalty.profile_id, half_penalty.version), self.storage)),
        ]

        self.assertEqual([exam.net for exam in exams], [11.0, 12.0, 10.0])
        self.assertEqual([exam.xp for exam in exams], [168, 168, 168])
        saved = self.storage.load_list("exams.json", Exam)
        self.assertEqual([exam.scoring_profile.profile_id for exam in saved], ["legacy-yks", no_penalty.profile_id, half_penalty.profile_id])

    def test_profile_edit_appends_version_without_rescoring_saved_exam(self):
        first = self.create_profile("Half", penalty="1/2")
        saved = asyncio.run(create_exam(payload(first.profile_id, first.version), self.storage))
        version_two = asyncio.run(update_profile(first.profile_id, ExamScoringProfileCreate(
            display_name="No penalty", country_label="Example",
            scoring_rule=ExamScoringRule(correct_points="1", wrong_penalty="0", blank_points="0"),
        ), self.storage))

        reread = self.storage.load_list("exams.json", Exam)[0]
        newer = asyncio.run(create_exam(payload(first.profile_id, version_two.version), self.storage))
        self.assertEqual((saved.scoring_profile.version, saved.net), (1, 10.0))
        self.assertEqual((reread.scoring_profile.version, reread.net), (1, 10.0))
        self.assertEqual((version_two.version, newer.net), (2, 12.0))
        versions = self.storage.load_list("exam_profiles.json", ExamScoringProfile)
        self.assertEqual([profile.version for profile in versions], [1, 2])

    def test_legacy_json_and_old_client_updates_default_or_preserve_profile(self):
        path = Path(self.temp_dir.name) / "exams.json"
        path.write_text(json.dumps([{
            "id": "legacy", "date": "2026-11-14", "subject": "Math",
            "correct": 12, "incorrect": 4, "blank": 4,
        }]), encoding="utf-8")
        legacy = self.storage.load_list("exams.json", Exam)[0]
        self.assertEqual((legacy.scoring_profile.profile_id, legacy.net, legacy.xp), ("legacy-yks", 11.0, 197))

        custom = self.create_profile("No penalty")
        saved = asyncio.run(create_exam(payload(custom.profile_id, custom.version), self.storage))
        old_client_payload = payload()
        edited = asyncio.run(update_exam(saved.id, old_client_payload, self.storage))
        self.assertEqual((edited.scoring_profile.profile_id, edited.net), (custom.profile_id, 12.0))

    def test_exact_rational_validation_and_profile_reference_validation(self):
        self.assertEqual(ExamScoringRule(correct_points="2/4").correct_points, "1/2")
        for value in ("1/0", "1.5", "-1/4", "x"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ExamScoringRule(wrong_penalty=value)
        with self.assertRaises(HTTPException) as unknown:
            asyncio.run(create_exam(payload("missing", 1), self.storage))
        self.assertEqual(unknown.exception.status_code, 422)

    def test_sections_apply_exact_rule_to_aggregated_counts_once(self):
        profile = self.create_profile("Thirds", correct="1/3", penalty="1/6", blank="1/12")
        sectioned = ExamCreate(
            date="2026-11-15", exam_type="ayt", subject="ignored", correct=0, incorrect=0, blank=0,
            sections=[
                {"subject": "A", "correct": 2, "incorrect": 1, "blank": 1},
                {"subject": "B", "correct": 3, "incorrect": 2, "blank": 1},
            ], scoring_profile_id=profile.profile_id, scoring_profile_version=profile.version,
        )
        created = asyncio.run(create_exam(sectioned, self.storage))
        self.assertEqual((created.correct, created.incorrect, created.blank), (5, 3, 2))
        self.assertAlmostEqual(created.net, 4 / 3)
        self.assertEqual(len(created.sections), 2)

    def test_profile_versions_and_legacy_exam_snapshot_survive_backup_restore(self):
        profile = self.create_profile("Half", penalty="1/2")
        saved = asyncio.run(create_exam(payload(profile.profile_id, profile.version), self.storage))
        self.storage.append_list("exams.json", Exam(
            id="old-json", date="2026-11-14", subject="Legacy", correct=12, incorrect=4, blank=4,
        ), Exam)
        archive = Path(self.temp_dir.name) / "profiles.zip"
        target = Path(self.temp_dir.name) / "restored"
        create_backup(self.temp_dir.name, archive)
        restore_backup(archive, target)
        restored = StorageService(target).load_list("exams.json", Exam)
        self.assertEqual([(exam.scoring_profile.profile_id, exam.net) for exam in restored], [
            (profile.profile_id, 10.0), ("legacy-yks", 11.0),
        ])
        self.assertEqual(StorageService(target).load_list("exam_profiles.json", ExamScoringProfile), [profile])
        self.assertEqual(saved.xp, 168)


if __name__ == "__main__":
    unittest.main()
