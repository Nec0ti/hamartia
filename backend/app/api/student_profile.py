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
    result = None

    def replace(current):
        nonlocal result
        if payload.revision != current.revision:
            raise HTTPException(status_code=409, detail="Student profile changed. Reload it before saving.")
        result = payload.model_copy(update={"revision": current.revision + 1})
        for field in StudentOnboarding.model_fields:
            setattr(current, field, getattr(result, field))
        return True

    storage.update_doc("onboarding.json", StudentOnboarding, replace)
    return result


@router.delete("", response_model=StudentOnboarding)
async def reset_student_profile(storage: StorageService = Depends(get_storage)):
    result = None

    def reset(current):
        nonlocal result
        result = StudentOnboarding(revision=current.revision + 1)
        for field in StudentOnboarding.model_fields:
            setattr(current, field, getattr(result, field))
        return True

    storage.update_doc("onboarding.json", StudentOnboarding, reset)
    return result
