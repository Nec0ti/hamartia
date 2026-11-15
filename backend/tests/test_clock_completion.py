"""Failure-injection coverage for retry-safe focused-practice completion."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import clock, practice
from app.services.storage import StorageError, StorageService


class FocusCompletionRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.clock_data = patch.object(clock, "DATA_DIR", self.data_dir)
        self.practice_data = patch.object(practice, "DATA_DIR", self.data_dir)
        self.clock_data.start()
        self.practice_data.start()
        app = FastAPI()
        app.include_router(clock.router)
        app.include_router(practice.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.practice_data.stop()
        self.clock_data.stop()
        self.temp.cleanup()

    def test_successful_create_then_failed_clock_clear_retries_without_duplicate(self):
        completion_id = str(uuid4())
        draft = {
            "date": "2026-11-15", "subject": "Mathematics", "topic": "Functions",
            "correct": 2, "incorrect": 1, "blank": 0, "completion_id": completion_id,
        }
        timer = {
            "kind": "practice", "status": "paused", "elapsed_ms": 9000,
            "practice_draft": draft,
        }
        initial = self.client.patch("/clock", json={"active_timer": timer})
        self.assertEqual(initial.status_code, 200)

        practice_payload = {**{key: value for key, value in draft.items() if key != "completion_id"},
                            "duration_seconds": 9}
        headers = {"Idempotency-Key": completion_id}
        first = self.client.post("/practice", json=practice_payload, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)

        with patch.object(StorageService, "update_doc", side_effect=StorageError("injected write failure")):
            failed_clear = self.client.patch("/clock", json={"active_timer": None})
        self.assertEqual(failed_clear.status_code, 500)
        self.assertEqual(self.client.get("/clock").json()["active_timer"]["practice_draft"]["completion_id"], completion_id)

        retried = self.client.post("/practice", json=practice_payload, headers=headers)
        self.assertEqual(retried.status_code, 201, retried.text)
        self.assertEqual(retried.json()["id"], first.json()["id"])
        self.assertEqual(len(self.client.get("/practice").json()), 1)

        cleared = self.client.patch("/clock", json={"active_timer": None})
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.json()["active_timer"])


if __name__ == "__main__":
    unittest.main()
