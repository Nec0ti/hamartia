"""ASGI entrypoint for the local development launcher."""

from app.desktop import DesktopOriginGuard, desktop_allowed_origins
from app.main import app

application = DesktopOriginGuard(app, allowed_origins=desktop_allowed_origins())
