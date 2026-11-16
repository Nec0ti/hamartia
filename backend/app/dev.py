"""ASGI entrypoint for the local development launcher."""

import os

from app.desktop import DesktopAuthGuard, DesktopOriginGuard, desktop_allowed_origins
from app.main import app

application = DesktopAuthGuard(
    DesktopOriginGuard(app, allowed_origins=desktop_allowed_origins()),
    required=bool(os.environ.get("HAMARTIA_CONTROL_TOKEN")),
)
