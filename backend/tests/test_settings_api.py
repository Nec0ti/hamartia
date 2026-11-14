import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings
from app.models.schemas import Settings
from app.services.storage import StorageService


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.storage = StorageService(self.data_dir)
        self.app = FastAPI()
        self.app.include_router(settings.router)
        self.client_context = patch.object(settings, "DATA_DIR", self.data_dir)
        self.client_context.start()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.client_context.stop()
        self.temp_dir.cleanup()

    def test_get_redacts_key_and_reports_presence(self):
        self.storage.save_doc("settings.json", Settings(api_key="secret-value"))

        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["has_api_key"], True)
        self.assertNotIn("api_key", response.json())
        self.assertNotIn("secret-value", response.text)

    def test_patch_without_key_preserves_existing_key_and_redacts_response(self):
        self.storage.save_doc("settings.json", Settings(api_key="existing-secret"))

        response = self.client.patch("/settings", json={
            "litellm_base_url": "http://localhost:4000/v1",
            "model_name": "local-model",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["has_api_key"], True)
        self.assertNotIn("existing-secret", response.text)
        self.assertEqual(self.storage.load_doc("settings.json", Settings).api_key, "existing-secret")

    def test_patch_can_replace_or_explicitly_clear_key(self):
        self.storage.save_doc("settings.json", Settings(api_key="old-secret"))

        replaced = self.client.patch("/settings", json={
            "litellm_base_url": "http://localhost:4000/v1",
            "model_name": "local-model",
            "api_key": "new-secret",
        })
        self.assertEqual(replaced.status_code, 200)
        self.assertEqual(self.storage.load_doc("settings.json", Settings).api_key, "new-secret")
        self.assertNotIn("new-secret", replaced.text)

        cleared = self.client.patch("/settings", json={
            "litellm_base_url": "http://localhost:4000/v1",
            "model_name": "local-model",
            "clear_api_key": True,
        })
        self.assertEqual(cleared.status_code, 200)
        self.assertFalse(cleared.json()["has_api_key"])
        self.assertEqual(self.storage.load_doc("settings.json", Settings).api_key, "")


if __name__ == "__main__":
    unittest.main()
