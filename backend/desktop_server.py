"""Run the loopback API and bundled frontend for the desktop application."""

import argparse
import sys
from pathlib import Path

import uvicorn

from app.desktop import configure_frontend, desktop_server_settings
from app.core.config import DATA_DIR
from app.main import app
from app.services.backup import BackupError, restore_backup
from app.services.data_lock import DataDirectoryBusy

configure_frontend(app)


def restore_backup_command(archive_path: Path, data_dir: Path = DATA_DIR):
    try:
        restore_backup(archive_path, data_dir)
    except DataDirectoryBusy:
        return 2, "Restore failed: the data directory is in use."
    except BackupError:
        return 1, "Restore failed: the backup is invalid or could not be applied."
    except OSError:
        return 1, "Restore failed: a file operation could not be completed."
    return 0, "Backup restored successfully."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run or maintain the Hamartia desktop backend")
    parser.add_argument("--restore-backup", type=Path, metavar="ZIP", help="restore a backup while Hamartia is stopped")
    args = parser.parse_args(argv)
    if args.restore_backup is not None:
        code, status = restore_backup_command(args.restore_backup)
        print(status, file=sys.stdout if code == 0 else sys.stderr)
        return code

    try:
        host, port = desktop_server_settings()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
