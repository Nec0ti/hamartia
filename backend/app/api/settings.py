"""Settings endpoints: read and update LiteLLM configuration."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import Settings, SettingsResponse, SettingsUpdate
from app.services.storage import StorageService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def _response(settings: Settings) -> SettingsResponse:
    return SettingsResponse(
        litellm_base_url=settings.litellm_base_url,
        model_name=settings.model_name,
        has_api_key=bool(settings.api_key),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(storage: StorageService = Depends(get_storage)):
    settings = storage.load_doc("settings.json", Settings) or Settings()
    return _response(settings)


@router.patch("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, storage: StorageService = Depends(get_storage)):
    """Persist LiteLLM configuration without returning its API key."""
    result = None

    def apply(settings: Settings):
        nonlocal result
        settings.litellm_base_url = payload.litellm_base_url
        settings.model_name = payload.model_name
        if payload.clear_api_key:
            settings.api_key = ""
        elif payload.api_key:
            settings.api_key = payload.api_key
        result = _response(settings)
        return True

    storage.update_doc("settings.json", Settings, apply)
    return result
