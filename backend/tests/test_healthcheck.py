import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import healthcheck
from app.desktop import DesktopAuthGuard


class HealthcheckTests(unittest.TestCase):
    def make_client(self):
        app = FastAPI()
        app.include_router(healthcheck.router)
        return TestClient(DesktopAuthGuard(app, required=True))

    def test_ready_keeps_unauthenticated_probe_without_disclosing_data_path(self):
        with TemporaryDirectory() as directory, patch("app.core.config.DATA_DIR", Path(directory)):
            with self.make_client() as client:
                response = client.get("/healthcheck/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_not_ready_returns_generic_error_without_exception_details(self):
        with patch("app.core.config.DATA_DIR", Path("/private/student-data")), \
                patch("app.services.storage.StorageService", side_effect=OSError("secret filesystem detail")):
            with self.make_client() as client:
                response = client.get("/healthcheck/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "not_ready",
            "error": "Data storage is unavailable.",
        })
        self.assertNotIn("/private/student-data", response.text)
        self.assertNotIn("secret filesystem detail", response.text)


if __name__ == "__main__":
    unittest.main()
