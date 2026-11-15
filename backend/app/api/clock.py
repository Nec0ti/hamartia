"""Validated local clock, alarm, and active study-timer state."""

from fastapi import APIRouter, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import ClockState
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/clock", tags=["clock"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Clock storage unavailable: {exc}") from exc


@router.get("", response_model=ClockState)
async def get_clock_state():
    try:
        state = get_storage().load_doc("clock.json", ClockState)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="Saved clock state is invalid") from exc
    return state or ClockState()


@router.patch("", response_model=ClockState)
async def update_clock_state(payload: ClockState):
    storage = get_storage()

    def replace(current):
        for name in ClockState.model_fields:
            setattr(current, name, getattr(payload, name))
        return True

    try:
        storage.update_doc("clock.json", ClockState, replace)
        return storage.load_doc("clock.json", ClockState) or ClockState()
    except StorageError as exc:
        raise HTTPException(status_code=500, detail="Saved clock state could not be updated") from exc
