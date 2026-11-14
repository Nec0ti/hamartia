import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from starlette.datastructures import Headers

from app.api import questions as question_api
from app.models.schemas import CouncilAnalysis, Question
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

    def upload(self, filename="question.png", content=b"png", content_type="image/png"):
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
        self.assertEqual((self.uploads / created.image_name).read_bytes(), b"png")
        self.assertTrue(created.image_name.startswith("q_"))

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

    def test_manual_tag_is_persisted_without_ai(self):
        self.storage.save_list("questions.json", [Question(
            id="q1", image_name="q.png", image_path="uploads/q.png",
        )])

        result = asyncio.run(question_api.tag_question(
            "q1", question_api.TagRequest(hamartia_tag="[Reading Slip]"), self.storage,
        ))

        self.assertEqual(result.hamartia_tag, "[Reading Slip]")
        self.assertEqual(self.storage.load_list("questions.json", Question)[0].hamartia_tag, "[Reading Slip]")

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
