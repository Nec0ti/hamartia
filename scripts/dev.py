"""Run the local API and web app together; Ctrl+C stops both."""

import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def handle_terminate(signum, frame):
    raise KeyboardInterrupt


def wait_for(url, process, name):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited before becoming ready")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {name}: {url}")


def stop(processes):
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    signal.signal(signal.SIGTERM, handle_terminate)
    missing = [name for name in ("fastapi", "uvicorn") if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError(f"Install backend/requirements.txt in the active Python environment (missing {', '.join(missing)})")
    npm = shutil.which("npm")
    if not npm or not (ROOT / "frontend/node_modules/.bin/vite").exists():
        raise RuntimeError("Run npm ci in frontend and make npm available on PATH")
    try:
        frontend_port = int(os.environ.get("HAMARTIA_FRONTEND_PORT", "5173"))
    except ValueError as error:
        raise RuntimeError("HAMARTIA_FRONTEND_PORT must be an integer") from error
    if not 1 <= frontend_port <= 65535:
        raise RuntimeError("HAMARTIA_FRONTEND_PORT must be between 1 and 65535")

    processes = []
    try:
        processes.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
        ))
        processes.append(subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=ROOT / "frontend",
        ))
        wait_for("http://127.0.0.1:8000/healthcheck/ready", processes[0], "API")
        frontend_url = f"http://127.0.0.1:{frontend_port}"
        wait_for(frontend_url, processes[1], "frontend")
        print(f"Hamartia hazır: {frontend_url}", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
    finally:
        stop(processes)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"Hamartia başlatılamadı: {error}", file=sys.stderr)
        sys.exit(1)
