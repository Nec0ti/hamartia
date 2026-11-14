import tempfile
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import backup
from app.models.schemas import Settings
from app.services.storage import StorageService


class BackupApiTests(unittest.TestCase):
    def test_download_returns_zip_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            StorageService(data_dir).save_doc("settings.json", Settings(api_key="secret"))
            app = FastAPI()
            app.include_router(backup.router)
            with patch.object(backup, "DATA_DIR", data_dir), TestClient(app) as client:
                response = client.get("/backup")

            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment; filename=\"hamartia-backup.zip\"", response.headers["content-disposition"])
            self.assertEqual(response.headers["content-type"], "application/zip")
            archive_path = data_dir.parent / "download.zip"
            archive_path.write_bytes(response.content)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(json.loads(archive.read("settings.json"))["api_key"], "")
            archive_path.unlink()


if __name__ == "__main__":
    unittest.main()
