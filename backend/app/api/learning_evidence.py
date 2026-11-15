"""CRUD for user-entered observations about completed suggested activities."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import LearningEvidence, LearningEvidenceCreate
from app.services.storage import StorageService

router = APIRouter(prefix="/learning-evidence", tags=["learning-evidence"])


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}") from exc


@router.get("", response_model=list[LearningEvidence])
async def list_evidence(storage: StorageService = Depends(get_storage)):
    return storage.load_list("learning_evidence.json", LearningEvidence)


@router.post("", status_code=201, response_model=LearningEvidence)
async def create_evidence(payload: LearningEvidenceCreate, storage: StorageService = Depends(get_storage)):
    record = LearningEvidence(
        id=f"learning_evidence_{uuid4().hex}",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **payload.model_dump(),
    )
    storage.append_list("learning_evidence.json", record, LearningEvidence)
    return record


@router.put("/{evidence_id}", response_model=LearningEvidence)
async def update_evidence(
    evidence_id: str,
    payload: LearningEvidenceCreate,
    storage: StorageService = Depends(get_storage),
):
    updated = []

    def replace(records):
        for index, record in enumerate(records):
            if record.id == evidence_id:
                records[index] = LearningEvidence(
                    id=record.id, created_at=record.created_at, **payload.model_dump(),
                )
                updated.append(records[index])
                return True
        return False

    if not storage.update_list("learning_evidence.json", LearningEvidence, replace):
        raise HTTPException(status_code=404, detail="Learning evidence not found")
    return updated[0]


@router.delete("/{evidence_id}")
async def delete_evidence(evidence_id: str, storage: StorageService = Depends(get_storage)):
    def remove(records):
        remaining = [record for record in records if record.id != evidence_id]
        if len(remaining) == len(records):
            return False
        records[:] = remaining
        return True

    if not storage.update_list("learning_evidence.json", LearningEvidence, remove):
        raise HTTPException(status_code=404, detail="Learning evidence not found")
    return {"deleted": evidence_id}
