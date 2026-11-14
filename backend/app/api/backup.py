"""Local data export endpoint."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.core.config import DATA_DIR
from app.services.backup import BackupError, create_backup

router = APIRouter(tags=["backup"])


@router.get("/backup")
def download_backup():
    """Download persisted records and uploads as a validated ZIP backup."""
    handle = tempfile.NamedTemporaryFile(prefix="hamartia-backup-", suffix=".zip", delete=False)
    path = Path(handle.name)
    handle.close()
    try:
        create_backup(DATA_DIR, path)
    except (BackupError, OSError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Yedek oluşturulamadı: {exc}") from exc
    return FileResponse(
        path,
        media_type="application/zip",
        filename="hamartia-backup.zip",
        background=BackgroundTask(path.unlink, missing_ok=True),
    )
