"""AI-free timing for the five persisted Study Agent CLI workflows."""

import argparse
import contextlib
import io
import json
import platform
import socket
import statistics
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_study_agent_cli import StudyAgentCliTests  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    def run_trial() -> float:
        suite = unittest.TestSuite([
            StudyAgentCliTests("test_jsonl_host_workflows_preview_before_explicit_approval_and_replay_once"),
        ])
        started = time.perf_counter()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network access")) as connect, \
                patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network access")) as connect_ex, \
                contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        if not result.wasSuccessful():
            raise AssertionError("A deterministic CLI workflow benchmark oracle failed.")
        connect.assert_not_called()
        connect_ex.assert_not_called()
        return (time.perf_counter() - started) * 1000

    run_trial()  # Warm Python imports and route registration before timing.
    elapsed = [run_trial() for _ in range(args.repeats)]
    ordered = sorted(elapsed)
    report = {
        "benchmark": "study_agent_cli_persisted_workflows",
        "repeats": args.repeats,
        "workflows": ["practice", "learning_evidence", "question", "exam", "sectioned_exam"],
        "records_per_trial": 5,
        "warmup_trials": 1,
        "measurement": "full JSONL draft, zero-write check, explicit approval, and exact replay for all five record types",
        "elapsed_ms": {
            "p50": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(len(ordered) * .95))],
        },
        "ai_included": False,
        "provider_calls": 0,
        "external_connect_attempts": 0,
        "machine": {"python": platform.python_version(), "platform": platform.platform()},
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output:
        args.json_output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
