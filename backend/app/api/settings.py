"""Settings endpoints: read and update LiteLLM configuration."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import Settings
from app.services.storage import StorageService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


@router.get("", response_model=Settings)
async def get_settings(storage: StorageService = Depends(get_storage)):
    settings = storage.load_doc("settings.json", Settings) or Settings()
    return settings


@router.patch("", response_model=Settings)
async def update_settings(payload: Settings, storage: StorageService = Depends(get_storage)):
    """Persist LiteLLM base URL, model name, and optional API key."""
    storage.save_doc("settings.json", payload)
    return payload
