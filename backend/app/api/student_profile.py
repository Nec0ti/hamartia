"""Local-only first-run progress and editable student profile."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import StudentOnboarding
from app.services.storage import StorageService

router = APIRouter(prefix="/student-profile", tags=["student-profile"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


@router.get("", response_model=StudentOnboarding)
async def get_student_profile(storage: StorageService = Depends(get_storage)):
    return storage.load_doc("onboarding.json", StudentOnboarding) or StudentOnboarding()


@router.put("", response_model=StudentOnboarding)
async def save_student_profile(payload: StudentOnboarding, storage: StorageService = Depends(get_storage)):
    storage.save_doc("onboarding.json", payload)
    return payload


@router.delete("", response_model=StudentOnboarding)
async def reset_student_profile(storage: StorageService = Depends(get_storage)):
    empty = StudentOnboarding()
    storage.save_doc("onboarding.json", empty)
    return empty
