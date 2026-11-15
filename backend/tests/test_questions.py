import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from openai import OpenAIError
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.api import questions as question_api
from app.models.schemas import CouncilAnalysis, CurriculumReference, Exam, Question
from app.services.storage import StorageService


class QuestionFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.uploads = self.root / "uploads"
        self.storage = StorageService(self.root)
        self.paths = (
            patch.object(question_api, "DATA_DIR", self.root),
            patch.object(question_api, "UPLOAD_DIR", self.uploads),
        )
        for item in self.paths:
            item.start()

    def tearDown(self):
        for item in reversed(self.paths):
            item.stop()
        self.temp_dir.cleanup()

    def upload(self, filename="question.png", content=b"\x89PNG\r\n\x1a\nfixture", content_type="image/png"):
        file = tempfile.SpooledTemporaryFile()
        file.write(content)
        file.seek(0)
        return UploadFile(
            filename=filename,
            file=file,
            headers=Headers({"content-type": content_type}),
        )

    def test_upload_keeps_image_and_question_history(self):
        existing = Question(id="old", image_name="old.png", image_path="uploads/old.png", subject="Math")
        self.storage.save_list("questions.json", [existing])

        created = asyncio.run(question_api.upload_question(
            self.upload("../../question.png"), "x + 2 = 4", "Matematik", "Denklemler", self.storage,
        ))
        saved = self.storage.load_list("questions.json", Question)

        self.assertEqual([item.id for item in saved], ["old", created.id])
        self.assertEqual(created.subject, "Matematik")
        self.assertEqual(created.topic, "Denklemler")
        self.assertEqual((self.uploads / created.image_name).read_bytes(), b"\x89PNG\r\n\x1a\nfixture")
        self.assertTrue(created.image_name.startswith("q_"))

    def test_text_only_question_is_saved_without_an_image(self):
        created = asyncio.run(question_api.upload_question(
            None, "f(x) = 2x + 1", "Matematik", "Fonksiyon", self.storage,
        ))

        saved = self.storage.load_list("questions.json", Question)
        self.assertEqual(created.ocr_text, "f(x) = 2x + 1")
        self.assertEqual(created.image_path, "")
        self.assertEqual(saved[0].id, created.id)
        self.assertFalse(self.uploads.exists())

    def test_legacy_question_defaults_to_empty_curriculum_reference(self):
        (self.root / "questions.json").write_text(json.dumps([{"id": "legacy", "ocr_text": "old record"}]))

        [question] = asyncio.run(question_api.list_questions(self.storage))

        self.assertEqual(question.curriculum_reference.model_dump(), CurriculumReference().model_dump())

    def test_user_entered_curriculum_reference_persists_on_question(self):
        reference = {
            "framework": "Türkiye Yüzyılı Maarif Modeli",
            "source": "MEB program note",
            "version": "2026",
            "grade_year": "9. sınıf",
            "unit_theme": "Fonksiyonlar",
            "learning_outcome": "Öğrenci fonksiyonları farklı gösterimlerle açıklar.",
            "process_component": "Problem çözme",
            "source_url": "https://tymm.meb.gov.tr/example",
        }
        created = asyncio.run(question_api.upload_question(
            None, "Question text", "Matematik", "Fonksiyonlar", self.storage,
            curriculum_reference_json=json.dumps(reference, ensure_ascii=False),
        ))

        saved = self.storage.load_list("questions.json", Question)[0]
        self.assertEqual(saved.curriculum_reference.model_dump(), reference)
        self.assertEqual(created.curriculum_reference.learning_outcome, reference["learning_outcome"])

    def test_invalid_curriculum_source_url_is_rejected_without_saving_question(self):
        for url in ("file:///etc/passwd", "https://example.test/outcome?token=secret", "https://example.test/outcome#fragment"):
            with self.subTest(url=url), self.assertRaises(HTTPException) as raised:
                asyncio.run(question_api.upload_question(
                    None, "Question text", "Matematik", "Fonksiyonlar", self.storage,
                    curriculum_reference_json=json.dumps({"source_url": url}),
                ))
            self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.storage.load_list("questions.json", Question), [])

    def test_model_provider_failure_is_visible_and_does_not_save_a_fake_analysis(self):
        self.storage.save_list("questions.json", [Question(id="q1", hamartia_tag="[Reading Slip]")])

        class OfflineModel:
            async def analyze_question(self, _question):
                raise OpenAIError("provider offline")

        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.analyze_question("q1", self.storage, OfflineModel()))

        saved = self.storage.load_list("questions.json", Question)[0]
        self.assertEqual(error.exception.status_code, 502)
        self.assertIn("OpenAIError", error.exception.detail)
        self.assertIsNone(saved.analysis)
        self.assertEqual(saved.hamartia_tag, "[Reading Slip]")

    def test_exam_question_metadata_round_trips_and_rejects_missing_exam(self):
        self.storage.save_list("exams.json", [Exam(
            id="exam1", date="2026-11-14", subject="Matematik", correct=7, incorrect=2, blank=1,
        )])
        created = asyncio.run(question_api.upload_question(
            None, "Fonksiyon sorusu", "Matematik", "Fonksiyon", self.storage,
            exam_id="exam1", question_number=8, solve_order=2, time_spent_seconds=45,
        ))

        saved = self.storage.load_list("questions.json", Question)[0]
        self.assertEqual((saved.exam_id, saved.question_number, saved.solve_order, saved.time_spent_seconds),
                         ("exam1", 8, 2, 45))
        self.assertEqual(created.exam_id, "exam1")

        with self.assertRaises(HTTPException) as missing:
            asyncio.run(question_api.upload_question(
                None, "Soru", "Matematik", "", self.storage, exam_id="missing",
            ))
        self.assertEqual(missing.exception.status_code, 404)

    def test_exam_question_metadata_cannot_exceed_exam_size(self):
        self.storage.save_list("exams.json", [Exam(
            id="exam1", date="2026-11-14", subject="Matematik", correct=7, incorrect=2, blank=1,
        )])

        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.upload_question(
                None, "Soru", "Matematik", "", self.storage,
                exam_id="exam1", question_number=11,
            ))
        self.assertEqual(error.exception.status_code, 422)

    def test_sectioned_exam_question_uses_selected_subject_size(self):
        exam = Exam(
            id="mock", date="2026-11-14", exam_type="tyt", subject="TYT Geneli",
            correct=30, incorrect=4, blank=16,
            sections=[
                {"subject": "Matematik", "correct": 10, "incorrect": 2, "blank": 8},
                {"subject": "Fen", "correct": 20, "incorrect": 2, "blank": 8},
                {"subject": "Din", "correct": 0, "incorrect": 0, "blank": 0},
            ],
        )
        self.storage.save_list("exams.json", [exam])

        created = asyncio.run(question_api.upload_question(
            None, "Fonksiyon sorusu", "matematik", "Fonksiyon", self.storage,
            exam_id="mock", question_number=20, solve_order=18, time_spent_seconds=42,
        ))
        self.assertEqual(created.exam_section_total, 20)

        with self.assertRaises(HTTPException) as out_of_section:
            asyncio.run(question_api.upload_question(
                None, "Soru", "Matematik", "", self.storage,
                exam_id="mock", question_number=21,
            ))
        with self.assertRaises(HTTPException) as unknown_subject:
            asyncio.run(question_api.upload_question(
                None, "Soru", "Fizik", "", self.storage, exam_id="mock",
            ))
        with self.assertRaises(HTTPException) as empty_section:
            asyncio.run(question_api.upload_question(
                None, "Soru", "Din", "", self.storage, exam_id="mock",
            ))
        self.assertEqual(out_of_section.exception.status_code, 422)
        self.assertEqual(unknown_subject.exception.status_code, 422)
        self.assertEqual(empty_section.exception.status_code, 422)

    def test_invalid_exam_reference_does_not_leave_uploaded_image(self):
        with self.assertRaises(HTTPException):
            asyncio.run(question_api.upload_question(
                self.upload(), "Soru", "Matematik", "", self.storage, exam_id="missing",
            ))

        self.assertFalse(self.uploads.exists())

    def test_legacy_question_json_defaults_order_fields(self):
        question = Question.model_validate({"id": "legacy", "subject": "Matematik"})

        self.assertEqual((question.exam_id, question.question_number, question.solve_order,
                          question.time_spent_seconds, question.exam_section_total),
                         ("", None, None, None, None))

    def test_upload_requires_either_an_image_or_text(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.upload_question(None, "  ", "Matematik", "", self.storage))
        self.assertEqual(error.exception.status_code, 422)

    def test_upload_rejects_symlinked_upload_root_without_writing_outside_data(self):
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        try:
            self.uploads.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(HTTPException) as error:
                asyncio.run(question_api.upload_question(
                    self.upload(), "Soru", "Matematik", "Fonksiyon", self.storage,
                ))
            self.assertEqual(error.exception.status_code, 500)
            self.assertIn("symbolic link", error.exception.detail)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(self.storage.load_list("questions.json", Question), [])
        finally:
            self.uploads.unlink(missing_ok=True)
            outside.rmdir()

    def test_delete_rejects_symlinked_upload_root_without_deleting_outside_file(self):
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        image = outside / "q1.png"
        image.write_bytes(b"keep")
        self.uploads.symlink_to(outside, target_is_directory=True)
        self.storage.save_list("questions.json", [Question(
            id="q1", image_name="q1.png", image_path="uploads/q1.png",
        )])
        try:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(question_api.delete_question("q1", self.storage))

            self.assertEqual(error.exception.status_code, 500)
            self.assertTrue(image.is_file())
            self.assertEqual([item.id for item in self.storage.load_list("questions.json", Question)], ["q1"])
        finally:
            self.uploads.unlink(missing_ok=True)
            image.unlink(missing_ok=True)
            outside.rmdir()

    def test_oversized_upload_is_rejected_without_creating_a_file_or_record(self):
        payload = b"\x89PNG\r\n\x1a\n" + b"x" * (question_api.MAX_UPLOAD_BYTES + 1)
        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.upload_question(
                self.upload(content=payload), "Soru", "Matematik", "Fonksiyon", self.storage,
            ))
        self.assertEqual(error.exception.status_code, 413)
        self.assertFalse(self.uploads.exists())
        self.assertEqual(self.storage.load_list("questions.json", Question), [])

    def test_image_route_serves_only_files_inside_upload_directory(self):
        self.uploads.mkdir()
        image = self.uploads / "q_test.png"
        image.write_bytes(b"png")
        self.storage.save_list("questions.json", [Question(
            id="q1", image_name=image.name, image_path="uploads/" + image.name,
        )])

        response = asyncio.run(question_api.get_question_image("q1", self.storage))
        self.assertEqual(Path(response.path), image)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

        escaped = Question(id="q2", image_name="secret", image_path="../../secret")
        self.storage.save_list("questions.json", [escaped])
        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.get_question_image("q2", self.storage))
        self.assertEqual(error.exception.status_code, 404)

    def test_image_route_rejects_symlinked_upload_root_and_image_file(self):
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.mkdir()
        external_image = outside / "q.png"
        external_image.write_bytes(b"private")
        try:
            self.uploads.symlink_to(outside, target_is_directory=True)
            self.storage.save_list("questions.json", [Question(
                id="outside-root", image_path="uploads/q.png", image_name="q.png",
            )])
            with self.assertRaises(HTTPException) as root_error:
                asyncio.run(question_api.get_question_image("outside-root", self.storage))
            self.assertEqual(root_error.exception.status_code, 404)
            self.uploads.unlink(missing_ok=True)

            self.uploads.mkdir()
            (self.uploads / "link.png").symlink_to(external_image)
            self.storage.save_list("questions.json", [Question(
                id="outside-file", image_path="uploads/link.png", image_name="link.png",
            )])
            with self.assertRaises(HTTPException) as file_error:
                asyncio.run(question_api.get_question_image("outside-file", self.storage))
            self.assertEqual(file_error.exception.status_code, 404)
        finally:
            if self.uploads.is_symlink():
                self.uploads.unlink(missing_ok=True)
            elif self.uploads.exists():
                for child in self.uploads.iterdir():
                    child.unlink(missing_ok=True)
                self.uploads.rmdir()
            external_image.unlink()
            outside.rmdir()

    def test_upload_rejects_unsupported_or_empty_files(self):
        with self.assertRaises(HTTPException) as unsupported:
            asyncio.run(question_api.upload_question(
                self.upload("question.svg", b"<svg/>", "image/svg+xml"), "", "", "", self.storage,
            ))
        self.assertEqual(unsupported.exception.status_code, 415)

        with self.assertRaises(HTTPException) as empty:
            asyncio.run(question_api.upload_question(
                self.upload(content=b""), "", "", "", self.storage,
            ))
        self.assertEqual(empty.exception.status_code, 422)

        with self.assertRaises(HTTPException) as mismatched:
            asyncio.run(question_api.upload_question(
                self.upload(content=b"not an image"), "", "", "", self.storage,
            ))
        self.assertEqual(mismatched.exception.status_code, 415)

    def test_manual_tag_is_persisted_without_ai(self):
        self.storage.save_list("questions.json", [Question(
            id="q1", image_name="q.png", image_path="uploads/q.png",
        )])

        result = asyncio.run(question_api.tag_question(
            "q1", question_api.TagRequest(hamartia_tag="[Reading Slip]"), self.storage,
        ))

        self.assertEqual(result.hamartia_tag, "[Reading Slip]")
        self.assertEqual(self.storage.load_list("questions.json", Question)[0].hamartia_tag, "[Reading Slip]")

    def test_edit_question_metadata_preserves_analysis_and_review_history(self):
        original = Question(
            id="q1", image_name="q.png", image_path="uploads/q.png", subject="Math", topic="Algebra",
            ocr_text="old text", hamartia_tag="[Reading Slip]", reviewed_at="2026-11-01",
            review_attempts=[{"attempted_at": "2026-11-01T00:00:00Z", "correct": False}],
        )
        self.storage.save_list("questions.json", [original])

        updated = asyncio.run(question_api.update_question(
            "q1", question_api.QuestionUpdate(subject=" Matematik ", topic=" Denklem ", ocr_text="new text"), self.storage,
        ))

        self.assertEqual((updated.subject, updated.topic, updated.ocr_text), ("Matematik", "Denklem", "new text"))
        self.assertEqual(updated.image_path, "uploads/q.png")
        self.assertEqual(updated.hamartia_tag, "[Reading Slip]")
        self.assertEqual(updated.reviewed_at, "2026-11-01")
        self.assertEqual(len(updated.review_attempts), 1)

    def test_edit_question_updates_curriculum_reference_and_omission_preserves_it(self):
        original = Question(
            id="q1", subject="Math", ocr_text="question",
            curriculum_reference={"framework": "Custom framework", "learning_outcome": "Recognize a pattern"},
        )
        self.storage.save_list("questions.json", [original])

        updated = asyncio.run(question_api.update_question(
            "q1", question_api.QuestionUpdate(
                subject="Math", topic="Patterns", ocr_text="edited question",
                curriculum_reference={"framework": "Custom framework", "learning_outcome": "Explain a pattern"},
            ), self.storage,
        ))
        self.assertEqual(updated.curriculum_reference.learning_outcome, "Explain a pattern")

        old_client_update = asyncio.run(question_api.update_question(
            "q1", question_api.QuestionUpdate(subject="Math", topic="Patterns", ocr_text="edited again"), self.storage,
        ))
        self.assertEqual(old_client_update.curriculum_reference.learning_outcome, "Explain a pattern")

        cleared = asyncio.run(question_api.update_question(
            "q1", question_api.QuestionUpdate(
                subject="Math", topic="Patterns", ocr_text="edited again", curriculum_reference={},
            ), self.storage,
        ))
        self.assertEqual(cleared.curriculum_reference.model_dump(), CurriculumReference().model_dump())

    def test_question_insights_include_bounded_reference_summaries_without_question_content(self):
        questions = [Question(
            id=f"q{index}", subject="Math", topic="Patterns", ocr_text=f"private question {index}",
            curriculum_reference={"framework": "Framework", "learning_outcome": f"Outcome {index}"},
        ) for index in range(10)]
        questions.append(Question(
            id="reviewed", subject="Math", reviewed_at="2026-11-15",
            curriculum_reference={"framework": "Framework", "learning_outcome": "Reviewed outcome"},
        ))
        self.storage.save_list("questions.json", questions)

        insights = asyncio.run(question_api.question_insights(self.storage))

        self.assertEqual(len(insights["curriculum_references"]), 8)
        self.assertEqual(insights["curriculum_references"][0]["learning_outcome"], "Outcome 9")
        self.assertNotIn("ocr_text", insights["curriculum_references"][0])
        self.assertNotIn("private question", json.dumps(insights["curriculum_references"]))

    def test_text_only_question_cannot_be_edited_to_empty_text(self):
        question = Question(id="q1", ocr_text="keep me")
        self.storage.save_list("questions.json", [question])

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(question_api.update_question(
                "q1", question_api.QuestionUpdate(subject="Math", topic="", ocr_text="  "), self.storage,
            ))

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.storage.load_list("questions.json", Question)[0].ocr_text, "keep me")

    def test_edit_missing_question_returns_404(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(question_api.update_question(
                "missing", question_api.QuestionUpdate(subject="Math", topic="", ocr_text="text"), self.storage,
            ))
        self.assertEqual(raised.exception.status_code, 404)

    def test_delete_question_removes_its_image_and_record(self):
        self.uploads.mkdir()
        image = self.uploads / "q1.png"
        image.write_bytes(b"image")
        self.storage.save_list("questions.json", [
            Question(id="q1", image_name="q1.png", image_path="uploads/q1.png"),
            Question(id="q2", ocr_text="keep"),
        ])

        result = asyncio.run(question_api.delete_question("q1", self.storage))

        self.assertEqual(result, {"deleted": "q1"})
        self.assertFalse(image.exists())
        self.assertEqual([item.id for item in self.storage.load_list("questions.json", Question)], ["q2"])

    def test_delete_question_does_not_remove_a_file_outside_uploads(self):
        outside = self.root / "private.txt"
        outside.write_text("keep")
        self.storage.save_list("questions.json", [Question(id="q1", image_path="../private.txt")])

        asyncio.run(question_api.delete_question("q1", self.storage))

        self.assertEqual(outside.read_text(), "keep")
        self.assertEqual(self.storage.load_list("questions.json", Question), [])

    def test_topic_insights_rank_repeated_mistakes_without_ai(self):
        self.storage.save_list("questions.json", [
            Question(id="q1", image_name="1.png", image_path="uploads/1.png", subject="Matematik", topic="Fonksiyon", hamartia_tag="[Knowledge Gap]", created_at="2026-11-01T12:00:00Z"),
            Question(id="q2", image_name="2.png", image_path="uploads/2.png", subject="matematik", topic="fonksiyon", hamartia_tag="[Reading Slip]", created_at="2026-11-05T12:00:00Z"),
            Question(id="q3", image_name="3.png", image_path="uploads/3.png", subject="Fizik", topic="Vektör", created_at="2026-11-04T12:00:00Z"),
        ])

        result = asyncio.run(question_api.question_insights(self.storage))

        self.assertEqual(result["total_questions"], 3)
        self.assertEqual(result["pending_questions"], 3)
        self.assertEqual(result["unclassified_questions"], 0)
        self.assertEqual(result["topics"][0]["pending_count"], 2)
        self.assertEqual(result["topics"][0]["last_seen"], "2026-11-05")
        self.assertEqual(result["topics"][0]["tags"], {"[Knowledge Gap]": 1, "[Reading Slip]": 1})
        self.assertTrue(result["reviews"][0]["has_image"])

    def test_review_action_removes_question_from_pending_plan(self):
        self.storage.save_list("questions.json", [
            Question(id="q1", image_name="1.png", image_path="uploads/1.png", subject="Matematik", topic="Fonksiyon"),
            Question(id="q2", image_name="2.png", image_path="uploads/2.png", subject="Matematik", topic="Fonksiyon"),
        ])

        reviewed = asyncio.run(question_api.review_question("q1", question_api.ReviewRequest(), self.storage))
        plan = asyncio.run(question_api.question_insights(self.storage))

        self.assertTrue(reviewed.reviewed_at.endswith("Z"))
        self.assertEqual(plan["total_questions"], 2)
        self.assertEqual(plan["pending_questions"], 1)
        self.assertEqual(plan["topics"][0]["pending_count"], 1)

        restored = asyncio.run(question_api.review_question(
            "q1", question_api.ReviewRequest(reviewed=False), self.storage,
        ))
        self.assertEqual(restored.reviewed_at, "")
        self.assertEqual(asyncio.run(question_api.question_insights(self.storage))["pending_questions"], 2)

    def test_solve_attempt_is_persisted_and_reopens_legacy_review(self):
        self.storage.save_list("questions.json", [Question(
            id="q1", image_name="1.png", image_path="uploads/1.png", reviewed_at="old-review",
        )])

        with patch.object(question_api, "_utcnow", return_value="2026-11-14T10:00:00Z"):
            result = asyncio.run(question_api.record_question_attempt(
                "q1", question_api.AttemptRequest(correct=False, attempt_day="2026-11-15"), self.storage,
            ))

        saved = self.storage.load_list("questions.json", Question)[0]
        self.assertEqual(result.review_attempts[0].attempted_at, "2026-11-14T10:00:00Z")
        self.assertEqual(result.review_attempts[0].attempt_day, "2026-11-15")
        self.assertFalse(saved.review_attempts[0].correct)
        self.assertEqual(saved.reviewed_at, "")

    def test_solve_attempt_returns_404_for_missing_question(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(question_api.record_question_attempt(
                "missing", question_api.AttemptRequest(correct=True, attempt_day="2026-11-14"), self.storage,
            ))
        self.assertEqual(error.exception.status_code, 404)

    def test_solve_attempt_omission_uses_utc_fallback_and_invalid_local_day_is_rejected(self):
        self.storage.save_list("questions.json", [Question(id="q1")])
        with patch.object(question_api, "_utcnow", return_value="2026-11-14T23:59:00Z"):
            result = asyncio.run(question_api.record_question_attempt(
                "q1", question_api.AttemptRequest(correct=True), self.storage,
            ))
        self.assertEqual(result.review_attempts[0].attempt_day, "2026-11-14")
        with self.assertRaises(ValidationError):
            question_api.AttemptRequest(correct=True, attempt_day="2026-02-30")

    def test_council_schema_reads_old_and_new_envelopes(self):
        legacy = CouncilAnalysis.model_validate({
            "dissenter": "old", "first_principles": "base", "verdict": {"difficulty": 3},
        })
        current = CouncilAnalysis.model_validate({
            "counselors": {"dissenter": "new"}, "verdict": {"difficulty": 4},
        })
        self.assertEqual(legacy.counselors.dissenter, "old")
        self.assertEqual(current.counselors.dissenter, "new")


if __name__ == "__main__":
    unittest.main()
