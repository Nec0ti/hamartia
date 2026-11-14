import asyncio
import threading
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


if __name__ == "__main__":
    unittest.main()
