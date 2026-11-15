"""JSON-lines entry point for Hamartia's read-only Study Agent CLI tool.

Run with ``PYTHONPATH=backend python -m app.hamartia_cli --jsonl``. Each input
line is one bounded JSON command and each output line is one JSON result. The
only supported command is ``study.practice.prepare``; this CLI cannot write,
update, delete, access settings, invoke a provider, or execute shell commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pydantic import ValidationError

from app.services.study_agent_cli import dispatch_cli

MAX_LINE_LENGTH = 256_000


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key.")
        result[key] = value
    return result


def run_json_line(line: str) -> dict[str, Any]:
    if len(line.encode("utf-8")) > MAX_LINE_LENGTH:
        return {"status": "error", "error": "request_too_large"}
    try:
        envelope = json.loads(line, object_pairs_hook=_unique_object)
        if not isinstance(envelope, dict):
            return {"status": "error", "error": "request_must_be_an_object"}
        return dispatch_cli(envelope)
    except (ValueError, ValidationError, TypeError):
        return {"status": "error", "error": "invalid_or_unsupported_command"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", action="store_true", required=True, help="read one JSON command per line")
    parser.parse_args(argv)
    stream = getattr(sys.stdin, "buffer", sys.stdin)
    while True:
        line = stream.readline(MAX_LINE_LENGTH + 1)
        if not line:
            break
        oversized = len(line) > MAX_LINE_LENGTH
        newline = b"\n" if isinstance(line, bytes) else "\n"
        while oversized and line and not line.endswith(newline):
            line = stream.readline(MAX_LINE_LENGTH + 1)
        if oversized:
            result = {"status": "error", "error": "request_too_large"}
        else:
            try:
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="strict")
                result = run_json_line(line)
            except UnicodeDecodeError:
                result = {"status": "error", "error": "invalid_or_unsupported_command"}
        sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
