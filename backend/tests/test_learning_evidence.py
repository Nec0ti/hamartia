import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unittest.mock import patch

from app.api import learning_evidence
from app.main import app
from app.models.schemas import LearningEvidence, LearningEvidenceCreate
from app.services.storage import StorageService


def payload(**updates):
    values = {
        "date": "2026-11-15", "subject": " Math ", "topic": " Quadratics ",
        "activity": "Solved three fresh examples", "observation": "I mixed up the signs at first.",
        "reference_url": " https://example.org/notes?q=1#work ",
    }
    values.update(updates)
    return LearningEvidenceCreate(**values)


class LearningEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = StorageService(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_fields_are_required_trimmed_and_links_are_http_only(self):
        record = payload()
        self.assertEqual((record.subject, record.topic, record.activity, record.observation), (
            "Math", "Quadratics", "Solved three fresh examples", "I mixed up the signs at first.",
        ))
        self.assertEqual(record.reference_url, "https://example.org/notes?q=1#work")
        for updates in (
            {"date": "15-11-2026"}, {"subject": " "}, {"topic": "\t"},
            {"activity": " "}, {"observation": " "}, {"reference_url": "javascript:alert(1)"},
            {"reference_url": "https://user:pass@example.org"}, {"activity": "x" * 501},
            {"observation": "x" * 3001},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                payload(**updates)

    def test_crud_persists_only_to_evidence_collection_and_preserves_identity(self):
        created = asyncio.run(learning_evidence.create_evidence(payload(), self.storage))
        self.assertTrue(created.id.startswith("learning_evidence_"))
        self.assertEqual(asyncio.run(learning_evidence.list_evidence(self.storage)), [created])
        self.assertTrue((Path(self.temp.name) / "learning_evidence.json").is_file())
        self.assertFalse((Path(self.temp.name) / "practice_sessions.json").exists())
        self.assertFalse((Path(self.temp.name) / "questions.json").exists())
        self.assertFalse((Path(self.temp.name) / "exams.json").exists())
        self.assertFalse((Path(self.temp.name) / "user.json").exists())

        updated = asyncio.run(learning_evidence.update_evidence(
            created.id, payload(date="2026-11-16", observation="The second method was clearer.", reference_url=""), self.storage,
        ))
        self.assertEqual((updated.id, updated.created_at, updated.date), (created.id, created.created_at, "2026-11-16"))
        self.assertEqual(updated.reference_url, "")
        self.assertEqual(asyncio.run(learning_evidence.delete_evidence(created.id, self.storage)), {"deleted": created.id})
        self.assertEqual(asyncio.run(learning_evidence.list_evidence(self.storage)), [])

    def test_missing_file_and_missing_record(self):
        self.assertEqual(asyncio.run(learning_evidence.list_evidence(self.storage)), [])
        with self.assertRaises(HTTPException) as update_error:
            asyncio.run(learning_evidence.update_evidence("missing", payload(), self.storage))
        self.assertEqual(update_error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as delete_error:
            asyncio.run(learning_evidence.delete_evidence("missing", self.storage))
        self.assertEqual(delete_error.exception.status_code, 404)

    def test_http_contract_validates_and_persists_without_ai_or_review_paths(self):
        data_dir = Path(self.temp.name) / "api-data"
        with patch.object(learning_evidence, "DATA_DIR", data_dir), patch("app.main.DATA_DIR", data_dir), TestClient(app) as client:
            response = client.post("/learning-evidence", json=payload().model_dump())
            self.assertEqual(response.status_code, 201)
            created = response.json()
            self.assertEqual(created["subject"], "Math")
            self.assertEqual(created["reference_url"], "https://example.org/notes?q=1#work")
            invalid_payload = payload().model_dump()
            invalid_payload["reference_url"] = "javascript:alert(1)"
            invalid = client.post("/learning-evidence", json=invalid_payload)
            self.assertEqual(invalid.status_code, 422)
            listed = client.get("/learning-evidence")
            self.assertEqual(listed.json(), [created])
            self.assertFalse((data_dir / "questions.json").exists())
            self.assertFalse((data_dir / "exams.json").exists())
            self.assertFalse((data_dir / "practice_sessions.json").exists())
            self.assertFalse((data_dir / "user.json").exists())


if __name__ == "__main__":
    unittest.main()
