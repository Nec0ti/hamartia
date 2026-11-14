"""Run the loopback API and bundled frontend for the desktop application."""

import sys

import uvicorn

from app.desktop import configure_frontend, desktop_server_settings
from app.main import app

configure_frontend(app)


def main():
    try:
        host, port = desktop_server_settings()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
