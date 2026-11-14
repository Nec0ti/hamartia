"""Exam CRUD with automated YKS Net and XP calculation.

Net and XP are derived on write/read through `core.formulas`, never stored,
so the JSON file only ever holds raw inputs.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import DATA_DIR
from app.models.schemas import Exam, ExamCreate
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


@router.post("", status_code=201, response_model=Exam)
async def create_exam(payload: ExamCreate, storage: StorageService = Depends(get_storage)):
    """Create an exam from UI inputs and preserve the student's history."""
    exam = Exam(
        id=f"exam_{uuid4().hex}",
        date=payload.date,
        exam_type=payload.exam_type,
        subject=payload.subject,
        correct=payload.correct,
        incorrect=payload.incorrect,
        blank=payload.blank,
        duration_minutes=payload.duration_minutes,
        duration_seconds=payload.duration_seconds,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    storage.append_list("exams.json", exam, Exam)
    return exam


@router.put("/{exam_id}", response_model=Exam)
async def update_exam(exam_id: str, payload: ExamCreate, storage: StorageService = Depends(get_storage)):
    updated = []

    def replace(exams):
        for index, exam in enumerate(exams):
            if exam.id == exam_id:
                data = payload.model_dump()
                data.update(id=exam.id, created_at=exam.created_at)
                exams[index] = Exam(**data)
                updated.append(exams[index])
                return True
        return False

    if not storage.update_list("exams.json", Exam, replace):
        raise HTTPException(status_code=404, detail="Exam not found")
    return updated[0]


@router.get("/{exam_id}", response_model=Exam)
async def get_exam(exam_id: str, storage: StorageService = Depends(get_storage)):
    exams = storage.load_list("exams.json", Exam)
    exam = next((e for e in exams if e.id == exam_id), None)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.delete("/{exam_id}", status_code=200)
async def delete_exam(exam_id: str, storage: StorageService = Depends(get_storage)):
    def remove(exams):
        filtered = [exam for exam in exams if exam.id != exam_id]
        if len(filtered) == len(exams):
            return False
        exams[:] = filtered
        return True

    if not storage.update_list("exams.json", Exam, remove):
        raise HTTPException(status_code=404, detail="Exam not found")
    return {"deleted": exam_id}
