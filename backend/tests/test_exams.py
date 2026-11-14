import asyncio
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import ValidationError

from app.api.exams import create_exam
from app.models.schemas import Exam, ExamCreate
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
            date="2026-11-14", subject="Physics", correct=6, incorrect=3, blank=2,
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

    def test_exam_input_rejects_blank_subject_and_negative_counts(self):
        base = {"date": "2026-11-14", "subject": "Math", "correct": 1, "incorrect": 0, "blank": 0}
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "subject": "   "})
        with self.assertRaises(ValidationError):
            ExamCreate(**{**base, "correct": -1})


if __name__ == "__main__":
    unittest.main()
