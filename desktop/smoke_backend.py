"""Smoke-test a frozen backend binary and its persistent local data directory."""

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, data=None, token=None):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Hamartia-Control-Token"] = token
    request = Request(url, data=body, headers=headers)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, response.read()
    except HTTPError as response:
        return response.code, response.read()


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    name = "hamartia-backend.exe" if os.name == "nt" else "hamartia-backend"
    executable = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "backend" / "dist" / "hamartia-backend" / name
    if not executable.is_file():
        raise SystemExit(f"Frozen backend executable not found: {executable}")

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    control_token = secrets.token_hex(32)
    with tempfile.TemporaryDirectory(prefix="hamartia-desktop-smoke-") as temp_dir:
        env = {
            **os.environ,
            "HAMARTIA_HOST": "127.0.0.1",
            "HAMARTIA_PORT": str(port),
            "HAMARTIA_DATA_DIR": str(Path(temp_dir) / "data"),
            "HAMARTIA_CONTROL_TOKEN": control_token,
        }

        def launch():
            return subprocess.Popen(
                [str(executable)], cwd=temp_dir, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )

        process = launch()
        started = time.perf_counter()
        exam = None
        try:
            deadline = started + 30
            while time.perf_counter() < deadline:
                if process.poll() is not None:
                    details = process.stderr.read().decode(errors="replace")
                    raise RuntimeError(f"Frozen backend exited early: {details}")
                try:
                    status, _ = request(f"{base_url}/healthcheck/ready")
                    if status == 200:
                        break
                except (OSError, URLError):
                    time.sleep(0.1)
            else:
                raise TimeoutError("Frozen backend did not become ready")

            startup_ms = round((time.perf_counter() - started) * 1000, 1)
            for route in ("/questions", "/backup"):
                status, _ = request(f"{base_url}{route}")
                if status != 401:
                    raise AssertionError(f"Unauthenticated {route} returned HTTP {status}")
            _, page = request(f"{base_url}/study-plan", token=control_token)
            if b'<div id="root"></div>' not in page:
                raise AssertionError("SPA fallback did not serve the frontend index")
            assets = re.findall(rb'(?:src|href)="(/assets/[^\"]+)"', page)
            if not assets:
                raise AssertionError("Frontend index did not reference built assets")
            for asset in assets:
                _, content = request(f"{base_url}{asset.decode()}", token=control_token)
                if not content:
                    raise AssertionError(f"Frontend asset is empty: {asset.decode()}")
            status, body = request(f"{base_url}/exams", {
                "date": "2026-11-14", "exam_type": "branch", "subject": "Matematik",
                "duration_minutes": 30, "correct": 5, "incorrect": 1, "blank": 1,
            }, token=control_token)
            if status != 201:
                raise AssertionError(f"Exam creation returned HTTP {status}")
            exam = json.loads(body)
        finally:
            stop(process)

        process = launch()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    details = process.stderr.read().decode(errors="replace")
                    raise RuntimeError(f"Frozen backend exited during restart: {details}")
                try:
                    request(f"{base_url}/healthcheck/ready")
                    break
                except (OSError, URLError):
                    time.sleep(0.1)
            else:
                raise TimeoutError("Frozen backend did not restart")
            _, body = request(f"{base_url}/exams", token=control_token)
            records = json.loads(body)
            if not any(item.get("id") == exam["id"] for item in records):
                raise AssertionError("Study data did not persist across backend restarts")
        finally:
            stop(process)

    print(json.dumps({
        "benchmark": "frozen_backend_startup_and_persistence",
        "startup_ms": startup_ms,
        "static_spa_fallback": True,
        "data_persisted_after_restart": True,
        "ai_included": False,
    }))


if __name__ == "__main__":
    main()
