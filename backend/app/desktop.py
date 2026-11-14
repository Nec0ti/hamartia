"""Desktop-only frontend serving and backend process settings."""

import ipaddress
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


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
    directory = frontend_directory()
    if directory is not None:
        mount_frontend(app, directory)
