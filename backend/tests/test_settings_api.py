import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import settings
from app.desktop import configure_frontend, desktop_server_settings, frontend_directory, mount_frontend
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
    def _guarded_upload_app(self):
        from fastapi import Request

        app = FastAPI()
        reached = []

        @app.post("/upload")
        async def upload(request: Request):
            reached.append(True)
            form = await request.form()
            return {"fields": list(form.keys())}

        configure_frontend(app)
        return app, reached

    def test_desktop_guard_rejects_cross_site_multipart_before_parsing(self):
        with patch.dict("os.environ", {"HAMARTIA_HOST": "127.0.0.1", "HAMARTIA_PORT": "8000"}):
            app, reached = self._guarded_upload_app()
        client = TestClient(app)
        response = client.post(
            "/upload",
            content=b"not a valid multipart body",
            headers={
                "content-type": "multipart/form-data; boundary=broken",
                "origin": "https://attacker.example",
                "sec-fetch-site": "cross-site",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(reached, [])
        client.close()

    def test_desktop_guard_allows_packaged_origin(self):
        with patch.dict("os.environ", {"HAMARTIA_HOST": "127.0.0.1", "HAMARTIA_PORT": "43127"}):
            app, _ = self._guarded_upload_app()
        client = TestClient(app)
        response = client.post(
            "/upload",
            data={"name": "desktop"},
            headers={"origin": "http://127.0.0.1:43127", "sec-fetch-site": "same-origin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"fields": ["name"]})
        client.close()

    def test_desktop_guard_allows_vite_dev_origin(self):
        with patch.dict("os.environ", {"HAMARTIA_HOST": "127.0.0.1", "HAMARTIA_PORT": "8000"}):
            app, _ = self._guarded_upload_app()
        client = TestClient(app)
        response = client.post(
            "/upload",
            data={"name": "dev"},
            headers={"origin": "http://localhost:5173", "sec-fetch-site": "same-site"},
        )
        self.assertEqual(response.status_code, 200)
        client.close()

    def test_desktop_guard_rejects_null_origin_but_preserves_originless_cli(self):
        with patch.dict("os.environ", {}, clear=True):
            app, _ = self._guarded_upload_app()
        client = TestClient(app)
        rejected = client.post("/upload", data={"name": "browser"}, headers={"origin": "null"})
        allowed = client.post("/upload", data={"name": "cli"})
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        client.close()

    def test_desktop_shutdown_rejects_missing_and_wrong_control_tokens(self):
        app = FastAPI()
        configure_frontend(app)
        stopped = []
        app.state.desktop_shutdown_callback = lambda: stopped.append(True)
        client = TestClient(app)
        with patch.dict("os.environ", {"HAMARTIA_CONTROL_TOKEN": "correct-token"}, clear=True):
            missing = client.post("/desktop/shutdown")
            wrong = client.post(
                "/desktop/shutdown",
                headers={"X-Hamartia-Control-Token": "wrong-token"},
            )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(stopped, [])
        client.close()

    def test_desktop_shutdown_accepts_valid_control_token_and_requests_graceful_exit(self):
        app = FastAPI()
        configure_frontend(app)
        stopped = []
        app.state.desktop_shutdown_callback = lambda: stopped.append(True)
        client = TestClient(app)
        with patch.dict("os.environ", {"HAMARTIA_CONTROL_TOKEN": "correct-token"}, clear=True):
            response = client.post(
                "/desktop/shutdown",
                headers={"X-Hamartia-Control-Token": "correct-token"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "shutting_down"})
        self.assertEqual(stopped, [True])
        client.close()

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
