"""Exercise and time clock API persistence plus backup/restore safeguards."""

import copy
import json
import statistics
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import clock as clock_api
from app.main import app
from app.models.schemas import ClockState
from app.services.backup import create_backup, restore_backup
from app.services.storage import StorageService
from benchmark_common import emit

REPEATS = 21
ALARM_COUNT = 128


def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def percentile(samples, percent):
    ordered = sorted(samples)
    return ordered[max(0, (len(ordered) * percent + 99) // 100 - 1)]


def measure(operation):
    operation()
    samples = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        operation()
        samples.append(time.perf_counter() - started)
    return {
        "samples": len(samples),
        "warmups": 1,
        "quantiles": "p50 is median; p95 is nearest-rank ceil(0.95*n), with no interpolation",
        "p50_seconds": round(statistics.median(samples), 6),
        "p95_seconds": round(percentile(samples, 95), 6),
    }


def fixture_state(timestamp):
    alarms = []
    for index in range(ALARM_COUNT):
        at = timestamp + 7 * 24 * 60 * 60 * 1000 + index * 60_000
        alarms.append({
            "id": f"alarm-{index:03d}", "label": f"Synthetic reminder {index}",
            "kind": "once", "one_off_at_ms": at, "local_time": "", "weekdays": [],
            "enabled": True, "next_at_ms": at, "overdue_at_ms": None, "last_fired_at_ms": None,
        })
    timer = {
        "kind": "countdown", "status": "running", "elapsed_ms": 0,
        "started_at_ms": None, "deadline_at_ms": timestamp + 60_000,
        "duration_ms": 60_000, "remaining_ms": 60_000, "work_duration_ms": 0,
        "break_duration_ms": 0, "phase": None, "cycle_enabled": False,
        "cycle_count": 0, "overdue_at_ms": None, "laps": [], "practice_draft": None,
    }
    return {
        "preferences": {
            "pomodoro_work_minutes": 25, "pomodoro_break_minutes": 5,
            "pomodoro_cycle": False, "notifications_opt_in": False,
        },
        "alarms": alarms,
        "active_timer": timer,
    }


def expected_state(timestamp):
    """Independent response oracle, deliberately duplicated from the request builder."""
    expected_alarms = []
    for number in range(128):
        instant = timestamp + 604_800_000 + number * 60_000
        expected_alarms.append({
            "id": f"alarm-{number:03d}",
            "label": f"Synthetic reminder {number}",
            "kind": "once",
            "one_off_at_ms": instant,
            "local_time": "",
            "weekdays": [],
            "enabled": True,
            "next_at_ms": instant,
            "overdue_at_ms": None,
            "last_fired_at_ms": None,
        })
    return {
        "preferences": {
            "pomodoro_work_minutes": 25,
            "pomodoro_break_minutes": 5,
            "pomodoro_cycle": False,
            "notifications_opt_in": False,
        },
        "alarms": expected_alarms,
        "active_timer": {
            "kind": "countdown",
            "status": "running",
            "elapsed_ms": 0,
            "started_at_ms": None,
            "deadline_at_ms": timestamp + 60_000,
            "duration_ms": 60_000,
            "remaining_ms": 60_000,
            "work_duration_ms": 0,
            "break_duration_ms": 0,
            "phase": None,
            "cycle_enabled": False,
            "cycle_count": 0,
            "overdue_at_ms": None,
            "laps": [],
            "practice_draft": None,
        },
    }


def main():
    with tempfile.TemporaryDirectory(prefix="hamartia-clock-api-bench-") as directory:
        data_dir = Path(directory) / "source"
        with patch.object(clock_api, "DATA_DIR", data_dir):
            client = TestClient(app)
            timestamp = now_ms()
            request_state = fixture_state(timestamp)
            expected = expected_state(timestamp)
            response = client.patch("/clock", json=request_state)
            assert response.status_code == 200, response.text
            assert response.json() == expected, "complete 128-alarm state must round-trip exactly"
            saved_path = data_dir / "clock.json"
            before_invalid_write = saved_path.read_bytes()
            invalid = copy.deepcopy(expected)
            invalid["alarms"][1]["id"] = invalid["alarms"][0]["id"]
            rejected = client.patch("/clock", json=invalid)
            assert rejected.status_code == 422, f"duplicate alarm identifiers should be rejected: {rejected.status_code}"
            assert saved_path.read_bytes() == before_invalid_write, "invalid PATCH changed the durable document"
            assert client.get("/clock").json() == expected

            patch_timing = measure(lambda: _assert_ok(client.patch("/clock", json=request_state)))
            get_timing = measure(lambda: _assert_json(client.get("/clock"), expected))

            archive_path = Path(directory) / "clock.zip"
            create_backup(data_dir, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                archived_state = json.loads(archive.read("clock.json"))
            restored_dir = Path(directory) / "restored"
            restore_backup(archive_path, restored_dir)
            restored_state = StorageService(restored_dir).load_doc("clock.json", ClockState).model_dump(mode="json")
            expected_restored = copy.deepcopy(archived_state)
            for alarm in expected_restored["alarms"]:
                alarm["enabled"] = False
            assert restored_state == expected_restored, "restore must disable alarms and preserve frozen timer state"
            assert restored_state["active_timer"]["status"] == "paused"
            assert all(not alarm["enabled"] for alarm in restored_state["alarms"])

            result = {
                "benchmark": "clock_api_persistence_and_backup",
                "repeats": REPEATS,
                "alarms": ALARM_COUNT,
                "api_patch_128_alarms": patch_timing,
                "api_get_128_alarms": get_timing,
                "round_trip": "full expected document equality for 128 distinct alarms and a running countdown",
                "failure_safety": "duplicate-ID PATCH returns 422 and byte-identical clock.json remains persisted",
                "backup_restore": "export freezes running countdown; restore disables all alarms and preserves exported frozen timer state",
                "timing_scope": "FastAPI TestClient route, Pydantic validation, and filesystem persistence; excludes loopback socket and concurrent-client latency",
                "ai_included": False,
            }
            emit(result)


def _assert_ok(response):
    assert response.status_code == 200, response.text


def _assert_json(response, expected):
    assert response.status_code == 200, response.text
    assert response.json() == expected


if __name__ == "__main__":
    main()
