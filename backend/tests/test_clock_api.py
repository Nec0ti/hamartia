"""Non-AI contract checks for persisted Clock state."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import clock
from app.models.schemas import ActiveClockTimer, ClockAlarm, ClockState, PracticeDraft
from app.services.storage import StorageService


def make_app(data_dir):
    app = FastAPI()
    app.include_router(clock.router)
    return app


class ClockApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.patch = patch.object(clock, "DATA_DIR", self.data_dir)
        self.patch.start()
        self.client = TestClient(make_app(self.data_dir))

    def tearDown(self):
        self.client.close()
        self.patch.stop()
        self.temp.cleanup()

    def test_get_missing_clock_document_returns_safe_defaults(self):
        response = self.client.get("/clock")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "preferences": {
                "pomodoro_work_minutes": 25,
                "pomodoro_break_minutes": 5,
                "pomodoro_cycle": False,
                "notifications_opt_in": False,
            },
            "alarms": [],
            "active_timer": None,
        })
        self.assertFalse((self.data_dir / "clock.json").exists())

    def test_patch_persists_state_and_get_returns_it(self):
        payload = ClockState(
            preferences={"pomodoro_work_minutes": 40, "notifications_opt_in": True},
            alarms=[ClockAlarm(
                id="alarm-1", label="Study start", kind="weekdays", local_time="07:15",
                weekdays=[0, 2, 4], enabled=True, next_at_ms=1_800_000_000_000,
            )],
            active_timer=ActiveClockTimer(
                kind="practice", status="running", started_at_ms=1_800_000_000_000,
                practice_draft=PracticeDraft(
                    date="2026-11-15", subject="Mathematics", topic="Functions", correct=2,
                ),
            ),
        )
        response = self.client.patch("/clock", json=payload.model_dump(mode="json"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/clock").json(), payload.model_dump(mode="json"))
        saved = json.loads((self.data_dir / "clock.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["active_timer"]["practice_draft"]["correct"], 2)

    def test_patch_replaces_deleted_alarms_and_timer(self):
        self.client.patch("/clock", json={"alarms": [{
            "id": "once-1", "label": "Reminder", "kind": "once",
            "one_off_at_ms": 1_800_000_000_000, "next_at_ms": 1_800_000_000_000,
        }]})
        response = self.client.patch("/clock", json={"alarms": [], "active_timer": None})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["alarms"], [])
        self.assertIsNone(response.json()["active_timer"])

    def test_clock_rejects_invalid_alarm_times_and_timer_state(self):
        invalid_alarm = self.client.patch("/clock", json={"alarms": [{
            "id": "bad", "label": "Bad time", "kind": "weekdays", "local_time": "25:90",
            "weekdays": [1], "next_at_ms": 1_800_000_000_000,
        }]})
        invalid_timer = self.client.patch("/clock", json={"active_timer": {
            "kind": "stopwatch", "status": "running", "elapsed_ms": 0,
        }})
        self.assertEqual(invalid_alarm.status_code, 422)
        self.assertEqual(invalid_timer.status_code, 422)

    def test_patch_rejects_duplicate_ids_and_mismatched_one_off_occurrence(self):
        duplicate_ids = self.client.patch("/clock", json={"alarms": [
            {"id": "same", "label": "One", "kind": "once", "one_off_at_ms": 10, "next_at_ms": 10},
            {"id": "same", "label": "Two", "kind": "once", "one_off_at_ms": 20, "next_at_ms": 20},
        ]})
        mismatched_next = self.client.patch("/clock", json={"alarms": [
            {"id": "once", "label": "One", "kind": "once", "one_off_at_ms": 10, "next_at_ms": 11},
        ]})
        self.assertEqual(duplicate_ids.status_code, 422)
        self.assertEqual(mismatched_next.status_code, 422)

    def test_invalid_patch_does_not_overwrite_valid_saved_clock(self):
        original = {"preferences": {"pomodoro_work_minutes": 35}}
        self.assertEqual(self.client.patch("/clock", json=original).status_code, 200)
        invalid = self.client.patch("/clock", json={"preferences": {"pomodoro_work_minutes": 0}})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.get("/clock").json()["preferences"]["pomodoro_work_minutes"], 35)

    def test_invalid_saved_clock_is_not_replaced_with_defaults(self):
        (self.data_dir / "clock.json").write_text("{broken", encoding="utf-8")
        response = self.client.get("/clock")
        self.assertEqual(response.status_code, 500)
        self.assertEqual((self.data_dir / "clock.json").read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
