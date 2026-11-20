import asyncio
import threading
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.exams import create_exam, delete_exam, update_exam
from app.models.schemas import Exam, ExamCreate, Settings, UserStats
from app.services.storage import StorageError, StorageService


class ExamFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = StorageService(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_appends_and_generates_missing_metadata(self):
        original = Exam(id="old", date="2026-11-01", subject="Math", correct=8, incorrect=2, blank=1)
        self.storage.save_list("exams.json", [original])
        payload = ExamCreate(
            date="2026-11-14", exam_type="ayt", subject="Physics", correct=6, incorrect=3, blank=2,
            duration_minutes=35, duration_seconds=12,
        )

        created = asyncio.run(create_exam(payload, self.storage))
        saved = self.storage.load_list("exams.json", Exam)

        self.assertEqual([exam.id for exam in saved[:1]], ["old"])
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[1].id, created.id)
        self.assertTrue(created.id.startswith("exam_"))
        self.assertTrue(created.created_at.endswith("Z"))
        self.assertEqual(created.subject, "Physics")
        self.assertEqual(created.exam_type, "ayt")

    def test_legacy_exam_defaults_to_branch_and_update_preserves_identity(self):
        original = Exam(id="old", date="2026-11-01", subject="Math", correct=8, incorrect=2, blank=1, created_at="old-time")
        self.storage.save_list("exams.json", [original])
        payload = ExamCreate(date="2026-11-14", exam_type="tyt", subject="Türkçe", correct=30, incorrect=2, blank=8)

        updated = asyncio.run(update_exam("old", payload, self.storage))

        self.assertEqual(updated.exam_type, "tyt")
        self.assertEqual(updated.subject, "Türkçe")
        self.assertEqual(updated.id, "old")
        self.assertEqual(updated.created_at, "old-time")
        raw = (Path(self.temp_dir.name) / "exams.json").read_text()
        self.assertEqual(Exam.model_validate_json(raw[1:-1]).exam_type, "tyt")

    def test_full_mock_create_and_edit_keeps_one_session_with_derived_totals(self):
        first = ExamCreate(
            date="2026-11-14", exam_type="tyt", subject="ignored",
            correct=0, incorrect=0, blank=0, duration_minutes=165,
            sections=[
                {"subject": " Türkçe ", "correct": 30, "incorrect": 5, "blank": 5},
                {"subject": "Matematik", "correct": 25, "incorrect": 8, "blank": 7},
            ],
        )
        created = asyncio.run(create_exam(first, self.storage))
        saved = self.storage.load_list("exams.json", Exam)

        self.assertEqual(len(saved), 1)
        self.assertEqual((created.subject, created.correct, created.incorrect, created.blank),
                         ("TYT Geneli", 55, 13, 12))
        self.assertEqual([section.subject for section in saved[0].sections], ["Türkçe", "Matematik"])
        self.assertEqual(created.net, 51.75)
        self.assertEqual(created.xp, 3733)

        update = ExamCreate(
            date="2026-11-14", exam_type="tyt", subject="TYT Geneli",
            correct=0, incorrect=0, blank=0, duration_minutes=160,
            sections=[
                {"subject": "Türkçe", "correct": 32, "incorrect": 4, "blank": 4},
                {"subject": "Matematik", "correct": 27, "incorrect": 7, "blank": 6},
            ],
        )
        edited = asyncio.run(update_exam(created.id, update, self.storage))

        self.assertEqual((edited.id, edited.created_at), (created.id, created.created_at))
        self.assertEqual((edited.correct, edited.incorrect, edited.blank), (59, 11, 10))
        self.assertEqual(len(self.storage.load_list("exams.json", Exam)), 1)

    def test_exam_sections_reject_duplicates_and_branch_sections(self):
        common = dict(date="2026-11-14", subject="exam", correct=0, incorrect=0, blank=0)
        with self.assertRaises(ValidationError):
            ExamCreate(exam_type="ayt", **common, sections=[
                {"subject": "Matematik", "correct": 1, "incorrect": 0, "blank": 0},
                {"subject": " matematik ", "correct": 1, "incorrect": 0, "blank": 0},
            ])
        with self.assertRaises(ValidationError):
            ExamCreate(exam_type="branch", **common, sections=[
                {"subject": "Fizik", "correct": 1, "incorrect": 0, "blank": 0},
            ])

    def test_custom_sectioned_exam_uses_user_name_custom_profile_and_round_trips(self):
        from app.api.exam_profiles import create_profile
        from app.models.schemas import ExamScoringProfileCreate, ExamScoringRule

        profile = asyncio.run(create_profile(ExamScoringProfileCreate(
            display_name="My rule", country_label="User context",
            scoring_rule=ExamScoringRule(correct_points="3/2", wrong_penalty="1/3", blank_points="0"),
        ), self.storage))
        payload = ExamCreate(
            date="2026-11-19", exam_type="custom", format_name="Personal mock",
            subject="ignored", correct=0, incorrect=0, blank=0, scoring_profile_id=profile.profile_id,
            scoring_profile_version=profile.version, sections=[
                {"subject": "Reading", "correct": 12, "incorrect": 2, "blank": 1},
                {"subject": "Quantitative reasoning", "correct": 8, "incorrect": 1, "blank": 3},
            ],
        )
        created = asyncio.run(create_exam(payload, self.storage))
        saved = self.storage.load_list("exams.json", Exam)[0]

        self.assertEqual((saved.exam_type, saved.format_name, saved.subject), ("custom", "Personal mock", "Personal mock"))
        self.assertEqual((saved.correct, saved.incorrect, saved.blank), (20, 3, 4))
        self.assertEqual(saved.scoring_profile.model_dump(), profile.model_dump())
        self.assertEqual(created.net, 29.0)
        self.assertEqual(len(saved.sections), 2)

        edited_payload = ExamCreate.model_validate(payload.model_dump() | {"format_name": "Edited mock"})
        edited = asyncio.run(update_exam(created.id, edited_payload, self.storage))
        self.assertEqual((edited.id, edited.format_name, edited.subject), (created.id, "Edited mock", "Edited mock"))
        self.assertEqual(edited.scoring_profile.model_dump(), profile.model_dump())

    def test_custom_sectioned_exam_requires_bounded_name_and_one_to_twelve_sections(self):
        common = dict(date="2026-11-19", exam_type="custom", subject="", correct=0, incorrect=0, blank=0)
        with self.assertRaises(ValidationError):
            ExamCreate(**common, sections=[{"subject": "A", "correct": 0, "incorrect": 0, "blank": 0}])
        with self.assertRaises(ValidationError):
            ExamCreate(**common, format_name=" ", sections=[{"subject": "A", "correct": 0, "incorrect": 0, "blank": 0}])
        with self.assertRaises(ValidationError):
            ExamCreate(**common, format_name="Mock", sections=[])
        with self.assertRaises(ValidationError):
            ExamCreate(**common, format_name="Mock", sections=[{"subject": f"S{i}", "correct": 0, "incorrect": 0, "blank": 0} for i in range(13)])
        with self.assertRaises(ValidationError):
            ExamCreate(**common, format_name="x" * 121, sections=[{"subject": "A", "correct": 0, "incorrect": 0, "blank": 0}])

    def test_update_and_delete_missing_exam_return_404(self):
        payload = ExamCreate(date="2026-11-14", subject="Math", correct=1, incorrect=0, blank=0)
        with self.assertRaises(HTTPException) as update_error:
            asyncio.run(update_exam("missing", payload, self.storage))
        with self.assertRaises(HTTPException) as delete_error:
            asyncio.run(delete_exam("missing", self.storage))
        self.assertEqual(update_error.exception.status_code, 404)
        self.assertEqual(delete_error.exception.status_code, 404)

    def test_delete_exam_removes_only_selected_record(self):
        self.storage.save_list("exams.json", [
            Exam(id="one", date="2026-11-01", subject="Math", correct=8, incorrect=2, blank=1),
            Exam(id="two", date="2026-11-02", subject="Physics", correct=6, incorrect=3, blank=2),
        ])

        result = asyncio.run(delete_exam("one", self.storage))

        self.assertEqual(result, {"deleted": "one"})
        self.assertEqual([exam.id for exam in self.storage.load_list("exams.json", Exam)], ["two"])

    def test_concurrent_appends_keep_all_records(self):
        def append(index):
            exam = Exam(id=f"exam-{index}", date="2026-11-14", subject="Math", correct=index, incorrect=0, blank=0)
            StorageService(Path(self.temp_dir.name)).append_list("exams.json", exam, Exam)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(append, range(32)))

        self.assertEqual(len(self.storage.load_list("exams.json", Exam)), 32)

    def test_invalid_json_is_not_overwritten(self):
        path = Path(self.temp_dir.name) / "exams.json"
        path.write_text("not json")

        with self.assertRaises(StorageError):
            self.storage.append_list("exams.json", Exam(
                id="new", date="2026-11-14", subject="Math", correct=1, incorrect=0, blank=0,
            ), Exam)

        self.assertEqual(path.read_text(), "not json")

    def test_invalid_json_read_raises_without_changing_source(self):
        path = Path(self.temp_dir.name) / "exams.json"
        path.write_text("not json")

        with self.assertRaises(StorageError):
            self.storage.load_list("exams.json", Exam)

        self.assertEqual(path.read_text(), "not json")

    def test_invalid_record_read_raises_without_discarding_records(self):
        path = Path(self.temp_dir.name) / "exams.json"
        raw = '[{"id":"old"}]'
        path.write_text(raw)

        with self.assertRaises(StorageError):
            self.storage.load_list("exams.json", Exam)

        self.assertEqual(path.read_text(), raw)

    def test_plain_dict_collections_round_trip(self):
        document = {"id": "doc-1", "filename": "notes.pdf"}

        self.storage.append_list("agent_documents.json", document, dict)

        self.assertEqual(self.storage.load_list("agent_documents.json", dict), [document])

    def test_concurrent_document_updates_keep_every_increment(self):
        def increment(_):
            def add(stats):
                stats.total_xp += 1
                return True
            self.storage.update_doc("user.json", UserStats, add)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(increment, range(32)))

        self.assertEqual(self.storage.load_doc("user.json", UserStats).total_xp, 32)

    def test_invalid_json_document_is_not_treated_as_missing(self):
        path = Path(self.temp_dir.name) / "settings.json"
        path.write_text("{")

        with self.assertRaises(StorageError):
            self.storage.load_doc("settings.json", Settings)

        self.assertEqual(path.read_text(), "{")

    def test_delete_and_append_cannot_lose_the_new_record(self):
        old = Exam(id="old", date="2026-11-14", subject="Math", correct=1, incorrect=0, blank=0)
        new = Exam(id="new", date="2026-11-14", subject="Physics", correct=1, incorrect=0, blank=0)
        self.storage.save_list("exams.json", [old])
        gate = threading.Barrier(2)

        def delete_old():
            gate.wait()

            def remove(exams):
                filtered = [exam for exam in exams if exam.id != "old"]
                if len(filtered) == len(exams):
                    return False
                exams[:] = filtered
                return True

            return self.storage.update_list("exams.json", Exam, remove)

        def append_new():
            gate.wait()
            self.storage.append_list("exams.json", new, Exam)

        with ThreadPoolExecutor(max_workers=2) as pool:
            delete_future = pool.submit(delete_old)
            append_future = pool.submit(append_new)
            delete_future.result()
            append_future.result()

        self.assertEqual([exam.id for exam in self.storage.load_list("exams.json", Exam)], ["new"])

    def test_exam_input_rejects_blank_subject_and_negative_counts(self):
        base = {"date": "2026-11-14", "subject": "Math", "correct": 1, "incorrect": 0, "blank": 0}
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "subject": "   "})
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "correct": -1})
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "date": "2026-02-30"})
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "duration_seconds": 60})
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "exam_type": "mock"})


if __name__ == "__main__":
    unittest.main()
