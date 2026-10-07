"""Exam CRUD with automated YKS Net and XP calculation.

Net and XP are derived on write/read through `core.formulas`, never stored,
so the JSON file only ever holds raw inputs.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import Exam
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/exams", tags=["exams"])


def get_storage():
    """Dependency returning the shared JSON storage service."""
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


@router.get("", response_model=list[Exam])
async def list_exams(storage: StorageService = Depends(get_storage)):
    return storage.load_list("exams.json", Exam)


@router.post("", status_code=201)
async def create_exam(payload: Exam, storage: StorageService = Depends(get_storage)):
    """Persist a new exam. Net and XP are computed but not stored."""
    # The payload already carries id/created_at; re-validate so the stored
    # shape exactly matches what the client sent.
    stored = Exam.model_validate(payload.model_dump())
    storage.save_list("exams.json", [stored])
    return stored


@router.get("/{exam_id}", response_model=Exam)
async def get_exam(exam_id: str, storage: StorageService = Depends(get_storage)):
    exams = storage.load_list("exams.json", Exam)
    exam = next((e for e in exams if e.id == exam_id), None)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.delete("/{exam_id}", status_code=200)
async def delete_exam(exam_id: str, storage: StorageService = Depends(get_storage)):
    exams = storage.load_list("exams.json", Exam)
    filtered = [e for e in exams if e.id != exam_id]
    if len(filtered) == len(exams):
        raise HTTPException(status_code=404, detail="Exam not found")
    storage.save_list("exams.json", filtered)
    return {"deleted": exam_id}
