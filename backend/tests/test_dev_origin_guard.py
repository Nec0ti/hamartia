import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import questions
from app.dev import application
from app.models.schemas import Question
from app.services.storage import StorageService


class DevOriginGuardTests(unittest.TestCase):
    def test_dev_entrypoint_rejects_hostile_upload_and_allows_vite(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            data_dir = Path(temporary_dir)
            uploads_dir = data_dir / "uploads"
            with patch.object(questions, "DATA_DIR", data_dir), \
                    patch.object(questions, "UPLOAD_DIR", uploads_dir), \
                    patch("app.main.DATA_DIR", data_dir), \
                    patch.dict("os.environ", {"HAMARTIA_HOST": "127.0.0.1", "HAMARTIA_PORT": "8000"}), \
                    TestClient(application) as client:
                upload = {"file": ("question.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")}
                hostile = client.post(
                    "/questions",
                    data={"ocr_text": "Question", "subject": "Math"},
                    files=upload,
                    headers={"origin": "https://attacker.example", "sec-fetch-site": "cross-site"},
                )
                self.assertEqual(hostile.status_code, 403)
                self.assertFalse((data_dir / "questions.json").exists())
                self.assertFalse(uploads_dir.exists())

                trusted = client.post(
                    "/questions",
                    data={"ocr_text": "Question", "subject": "Math"},
                    files=upload,
                    headers={"origin": "http://localhost:5173", "sec-fetch-site": "same-site"},
                )
                self.assertEqual(trusted.status_code, 201)
                stored = StorageService(data_dir).load_list("questions.json", Question)
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0].ocr_text, "Question")
                self.assertEqual(len(list(uploads_dir.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
