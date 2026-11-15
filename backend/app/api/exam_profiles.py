"""Append-only scoring-profile versions for user-defined exam rules."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import ExamScoringProfile, ExamScoringProfileCreate, legacy_yks_profile
from app.services.storage import StorageService

router = APIRouter(prefix="/exam-profiles", tags=["exam profiles"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def profile_versions(storage: StorageService) -> list[ExamScoringProfile]:
    custom = storage.load_list("exam_profiles.json", ExamScoringProfile)
    return [legacy_yks_profile(), *sorted(custom, key=lambda item: (item.profile_id, item.version))]


def resolve_profile(storage: StorageService, profile_id: str | None, version: int | None) -> ExamScoringProfile:
    if profile_id is None and version is None:
        return legacy_yks_profile()
    if profile_id is None or version is None:
        raise HTTPException(status_code=422, detail="Scoring profile ID and version are both required")
    profile = next((item for item in profile_versions(storage) if item.profile_id == profile_id and item.version == version), None)
    if profile is None:
        raise HTTPException(status_code=422, detail="Unknown scoring profile version")
    return profile


@router.get("", response_model=list[ExamScoringProfile])
async def list_profiles(storage: StorageService = Depends(get_storage)):
    return profile_versions(storage)


@router.post("", status_code=201, response_model=ExamScoringProfile)
async def create_profile(payload: ExamScoringProfileCreate, storage: StorageService = Depends(get_storage)):
    profile = ExamScoringProfile(
        profile_id=f"profile_{uuid4().hex}", version=1,
        display_name=payload.display_name, country_label=payload.country_label,
        scoring_rule=payload.scoring_rule,
    )
    storage.append_list("exam_profiles.json", profile, ExamScoringProfile)
    return profile


@router.put("/{profile_id}", response_model=ExamScoringProfile)
async def update_profile(profile_id: str, payload: ExamScoringProfileCreate, storage: StorageService = Depends(get_storage)):
    if profile_id == "legacy-yks":
        raise HTTPException(status_code=422, detail="The legacy YKS scoring profile is immutable")
    created: list[ExamScoringProfile] = []

    def append_version(profiles: list[ExamScoringProfile]) -> bool:
        matching = [item.version for item in profiles if item.profile_id == profile_id]
        if not matching:
            return False
        created.append(ExamScoringProfile(
            profile_id=profile_id, version=max(matching) + 1,
            display_name=payload.display_name, country_label=payload.country_label,
            scoring_rule=payload.scoring_rule,
        ))
        profiles.append(created[0])
        return True

    if not storage.update_list("exam_profiles.json", ExamScoringProfile, append_version):
        raise HTTPException(status_code=404, detail="Scoring profile not found")
    return created[0]
