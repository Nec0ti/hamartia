import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings
from app.desktop import desktop_server_settings, frontend_directory, mount_frontend
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


class DesktopServerTests(unittest.TestCase):
    def test_frontend_directory_uses_override_or_pyinstaller_bundle(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(sys, "frozen", False, create=True):
            self.assertIsNone(frontend_directory())
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"HAMARTIA_STATIC_DIR": temp_dir}, clear=True):
                self.assertEqual(frontend_directory(), Path(temp_dir).resolve())
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "_MEIPASS", "/bundle", create=True),
        ):
            self.assertEqual(frontend_directory(), Path("/bundle/frontend/dist"))

    def test_server_settings_default_to_loopback_and_validate_env(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(desktop_server_settings(), ("127.0.0.1", 8000))
        with patch.dict("os.environ", {"HAMARTIA_HOST": "0.0.0.0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "loopback"):
                desktop_server_settings()
        with patch.dict("os.environ", {"HAMARTIA_PORT": "70000"}, clear=True):
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                desktop_server_settings()

    def test_frontend_serves_assets_and_spa_routes(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "assets").mkdir()
            (root / "index.html").write_text("<main>Hamartia</main>")
            (root / "assets" / "app.js").write_text("window.ready = true")
            app = FastAPI()
            mount_frontend(app, root)
            client = TestClient(app)
            self.assertEqual(client.get("/").text, "<main>Hamartia</main>")
            self.assertEqual(client.get("/study-plan").text, "<main>Hamartia</main>")
            self.assertEqual(client.get("/assets/app.js").text, "window.ready = true")
            self.assertEqual(client.get("/assets/missing.js").status_code, 404)
            client.close()


if __name__ == "__main__":
    unittest.main()
