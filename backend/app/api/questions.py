"""Question (Mistake Vault) endpoints.

Handles image upload, OCR text capture, council-analysis triggering, and
mistake-tagging. The AI pipeline lives in `services/ai_service`.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from app.core.config import DATA_DIR, HAMARTIA_TAGS
from app.models.schemas import Question
from app.services.ai_service import AIService, get_ai
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/questions", tags=["questions"])
UPLOAD_DIR = DATA_DIR / "uploads"


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@router.post("", status_code=201)
async def upload_question(
    file: UploadFile = File(...),
    ocr_text: str = Form(""),
    storage: StorageService = Depends(get_storage),
):
    """Store an uploaded question image and its OCR text."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "img"
    safe_name = f"q_{_utcnow().replace(':', '')}.{ext}"
    path = UPLOAD_DIR / safe_name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        contents = await file.read()
        if contents:
            path.write_bytes(contents)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save upload: {exc}")

    question = Question(
        id=f"q_{_utcnow().replace(':', '')}",
        image_name=safe_name,
        image_path=str(path.relative_to(DATA_DIR)),
        ocr_text=ocr_text or "",
        created_at=_utcnow(),
    )
    questions = storage.load_list("questions.json", Question)
    questions.append(question)
    storage.save_list("questions.json", questions)
    return question


@router.get("", response_model=list[Question])
async def list_questions(storage: StorageService = Depends(get_storage)):
    return storage.load_list("questions.json", Question)


@router.get("/{question_id}", response_model=Question)
async def get_question(question_id: str, storage: StorageService = Depends(get_storage)):
    questions = storage.load_list("questions.json", Question)
    q = next((x for x in questions if x.id == question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.post("/{question_id}/analyze", response_model=Question)
async def analyze_question(
    question_id: str,
    storage: StorageService = Depends(get_storage),
    ai: AIService = Depends(get_ai),
):
    """Run the Council of Minds and attach the five-counselor verdict."""
    questions = storage.load_list("questions.json", Question)
    q = next((x for x in questions if x.id == question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    analysis = await ai.analyze_question(q)
    q.analysis = analysis
    q.hamartia_tag = analysis.verdict.hamartia_tag
    storage.save_list("questions.json", questions)
    return q


class TagRequest(BaseModel):
    hamartia_tag: str


@router.patch("/{question_id}/tag", response_model=Question)
async def tag_question(
    question_id: str,
    tag: TagRequest = Body(...),
    storage: StorageService = Depends(get_storage),
):
    """Assign a mistake tag from the allowed taxonomy."""
    tag = tag.hamartia_tag.strip()
    if tag not in HAMARTIA_TAGS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid tag. Allowed: {', '.join(HAMARTIA_TAGS)}",
        )
    questions = storage.load_list("questions.json", Question)
    for q in questions:
        if q.id == question_id:
            q.hamartia_tag = tag
            storage.save_list("questions.json", questions)
            return q
    raise HTTPException(status_code=404, detail="Question not found")
