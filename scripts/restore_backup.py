"""Restore a Hamartia ZIP backup while the app is stopped."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import DATA_DIR
from app.services.backup import BackupError, restore_backup
from app.services.data_lock import DataDirectoryBusy


def main():
    parser = argparse.ArgumentParser(description="Restore a Hamartia backup ZIP")
    parser.add_argument("archive", type=Path, help="Path to hamartia-backup.zip")
    args = parser.parse_args()
    try:
        result = restore_backup(args.archive, DATA_DIR)
    except DataDirectoryBusy:
        parser.error("Önce Hamartia'yı kapatıp tekrar deneyin.")
    except (BackupError, OSError) as error:
        parser.error(str(error))
    print("Yedek geri yüklendi.")
    if result["snapshot"]:
        print(f"Önceki veri klasörü: {result['snapshot']}")
    print("Bu bilgisayarın yerel AI API anahtarı korundu.")


if __name__ == "__main__":
    main()
