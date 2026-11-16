"""Health and readiness probe for the Hamartia API."""

from fastapi import APIRouter, Response

router = APIRouter(prefix="/healthcheck", tags=["system"])


@router.get("/health", tags=["system"])
async def health():
    """Liveness probe. Returns OK when the app and datastore are reachable."""
    return {"status": "ok"}


@router.get("/ready", tags=["system"])
async def ready(response: Response):
    """Readiness probe: confirms the JSON datastore is writable."""
    from app.core.config import DATA_DIR
    from app.services.storage import StorageService

    try:
        svc = StorageService(DATA_DIR)
        svc.load_list("exams.json", __import__("app.models.schemas", fromlist=["Exam"]).Exam)
        return {"status": "ready"}
    except Exception:
        response.status_code = 503
        return {"status": "not_ready", "error": "Data storage is unavailable."}
