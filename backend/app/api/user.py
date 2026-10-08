"""User progression profile (XP, level, streak, radar).

Reads/writes backend/data/user.json via the UserStats schema. This is the
source of truth for gamification state; the Settings endpoint only serves
the LiteLLM proxy configuration, never progression data.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import UserStats
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/user", tags=["profile"])


def get_storage():
    """Dependency returning the shared JSON storage service."""
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


@router.get("", response_model=UserStats)
async def get_user(storage: StorageService = Depends(get_storage)):
    stats = storage.load_doc("user.json", UserStats) or UserStats()
    return stats


@router.patch("", response_model=UserStats)
async def update_user(payload: UserStats, storage: StorageService = Depends(get_storage)):
    storage.save_doc("user.json", payload)
    return payload
