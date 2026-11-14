"""Desktop-only frontend serving and backend process settings."""

import ipaddress
import hmac
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse


VITE_ORIGINS = frozenset({
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
})


class DesktopOriginGuard:
    """Reject browser cross-site writes to the loopback desktop API."""

    def __init__(self, app, allowed_origins):
        self.app = app
        self.allowed_origins = allowed_origins

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        origin = headers.get(b"origin")
        fetch_site = headers.get(b"sec-fetch-site")
        rejected = origin is not None and (
            origin == b"null" or origin.decode("latin-1") not in self.allowed_origins
        )
        if fetch_site is not None and fetch_site.lower() not in {b"same-origin", b"same-site"}:
            rejected = True

        if rejected:
            response = PlainTextResponse("Cross-origin desktop API requests are not allowed.", status_code=403)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def desktop_allowed_origins():
    try:
        host, port = desktop_server_settings()
    except ValueError:
        # Keep desktop_server importable so its CLI can report invalid env settings.
        return VITE_ORIGINS
    if ":" in host:
        host = f"[{host}]"
    return VITE_ORIGINS | {f"http://{host}:{port}"}


def desktop_server_settings():
    host = os.environ.get("HAMARTIA_HOST", "127.0.0.1")
    port_text = os.environ.get("HAMARTIA_PORT", "8000")
    try:
        address = ipaddress.ip_address(host)
        port = int(port_text)
    except ValueError as error:
        raise ValueError("HAMARTIA_HOST must be a loopback IP and HAMARTIA_PORT an integer") from error
    if not address.is_loopback:
        raise ValueError("HAMARTIA_HOST must be a loopback IP")
    if not 1 <= port <= 65535:
        raise ValueError("HAMARTIA_PORT must be between 1 and 65535")
    return host, port


def frontend_directory():
    configured = os.environ.get("HAMARTIA_STATIC_DIR")
    if configured:
        return Path(configured).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "frontend" / "dist"
    return None


def mount_frontend(app: FastAPI, directory: Path):
    root = Path(directory).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"Frontend build not found: {index}")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend(path: str = ""):
        candidate = (root / path).resolve()
        if root not in candidate.parents and candidate != root:
            raise HTTPException(status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        if Path(path).suffix:
            raise HTTPException(status_code=404)
        return FileResponse(index)


def configure_frontend(app: FastAPI):
    app.add_middleware(DesktopOriginGuard, allowed_origins=desktop_allowed_origins())

    @app.post("/desktop/shutdown", include_in_schema=False)
    async def shutdown_desktop_backend(x_hamartia_control_token: str | None = Header(default=None)):
        expected = os.environ.get("HAMARTIA_CONTROL_TOKEN", "")
        if not expected or not x_hamartia_control_token or not hmac.compare_digest(
            expected, x_hamartia_control_token
        ):
            raise HTTPException(status_code=403, detail="Invalid desktop control token")
        callback = getattr(app.state, "desktop_shutdown_callback", None)
        if callback is None:
            raise HTTPException(status_code=503, detail="Desktop shutdown is unavailable")
        callback()
        return {"status": "shutting_down"}

    directory = frontend_directory()
    if directory is not None:
        mount_frontend(app, directory)
