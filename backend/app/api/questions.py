"""Question (Mistake Vault) endpoints.

Handles image upload, OCR text capture, council-analysis triggering, and
mistake-tagging. The AI pipeline lives in `services/ai_service`.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import FileResponse

from app.core.config import DATA_DIR, HAMARTIA_TAGS
from app.core.study_plan import topic_priorities
from app.models.schemas import Question, ReviewAttempt
from app.services.ai_service import AIService, get_ai
from app.services.storage import StorageError, StorageService

router = APIRouter(prefix="/questions", tags=["questions"])
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


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
    subject: str = Form(""),
    topic: str = Form(""),
    storage: StorageService = Depends(get_storage),
):
    """Store an uploaded question image, OCR text, and study labels."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in IMAGE_TYPES or file.content_type not in (None, "", IMAGE_TYPES[ext]):
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP image")
    safe_name = f"q_{uuid4().hex}{ext}"
    path = UPLOAD_DIR / safe_name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read upload: {exc}")
    if not contents:
        raise HTTPException(status_code=422, detail="Image is empty")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB")
    valid_signature = (
        contents.startswith(b"\x89PNG\r\n\x1a\n") if ext == ".png" else
        contents.startswith(b"\xff\xd8\xff") if ext in (".jpg", ".jpeg") else
        contents.startswith(b"RIFF") and contents[8:12] == b"WEBP"
    )
    if not valid_signature:
        raise HTTPException(status_code=415, detail="Image contents do not match PNG, JPEG, or WebP")
    try:
        path.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not save upload: {exc}")

    question = Question(
        id=f"q_{uuid4().hex}",
        image_name=safe_name,
        image_path=(Path("uploads") / safe_name).as_posix(),
        ocr_text=ocr_text or "",
        subject=subject.strip(),
        topic=topic.strip(),
        created_at=_utcnow(),
    )
    try:
        storage.append_list("questions.json", question, Question)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return question


@router.get("", response_model=list[Question])
async def list_questions(storage: StorageService = Depends(get_storage)):
    return storage.load_list("questions.json", Question)


@router.get("/insights", response_model=dict)
async def question_insights(storage: StorageService = Depends(get_storage)):
    """Rank repeated mistake topics without calling a model."""
    return topic_priorities(storage.load_list("questions.json", Question))


@router.get("/{question_id}", response_model=Question)
async def get_question(question_id: str, storage: StorageService = Depends(get_storage)):
    questions = storage.load_list("questions.json", Question)
    q = next((x for x in questions if x.id == question_id), None)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.get("/{question_id}/image")
async def get_question_image(question_id: str, storage: StorageService = Depends(get_storage)):
    questions = storage.load_list("questions.json", Question)
    question = next((item for item in questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    path = (DATA_DIR / question.image_path).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Question image not found")
    return FileResponse(path, headers={"X-Content-Type-Options": "nosniff"})


@router.post("/{question_id}/analyze", response_model=Question)
async def analyze_question(
    question_id: str,
    storage: StorageService = Depends(get_storage),
    ai: AIService = Depends(get_ai),
):
    """Run the Council of Minds and attach the five-counselor verdict."""
    questions = storage.load_list("questions.json", Question)
    question = next((item for item in questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    analysis = await ai.analyze_question(question)
    updated = []

    def save_analysis(items):
        for item in items:
            if item.id == question_id:
                item.analysis = analysis
                item.hamartia_tag = analysis.verdict.hamartia_tag
                updated.append(item)
                return True
        return False

    if not storage.update_list("questions.json", Question, save_analysis):
        raise HTTPException(status_code=404, detail="Question not found")
    return updated[0]


class TagRequest(BaseModel):
    hamartia_tag: str


class ReviewRequest(BaseModel):
    reviewed: bool = True


class AttemptRequest(BaseModel):
    correct: bool


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
    updated = []

    def save_tag(questions):
        for question in questions:
            if question.id == question_id:
                question.hamartia_tag = tag
                updated.append(question)
                return True
        return False

    if not storage.update_list("questions.json", Question, save_tag):
        raise HTTPException(status_code=404, detail="Question not found")
    return updated[0]


@router.patch("/{question_id}/review", response_model=Question)
async def review_question(
    question_id: str,
    payload: ReviewRequest,
    storage: StorageService = Depends(get_storage),
):
    """Set or clear review status without removing the saved question."""
    updated = []

    def mark_reviewed(questions):
        for question in questions:
            if question.id == question_id:
                question.reviewed_at = _utcnow() if payload.reviewed else ""
                updated.append(question)
                return True
        return False

    if not storage.update_list("questions.json", Question, mark_reviewed):
        raise HTTPException(status_code=404, detail="Question not found")
    return updated[0]


@router.post("/{question_id}/attempt", response_model=Question)
async def record_question_attempt(
    question_id: str,
    payload: AttemptRequest,
    storage: StorageService = Depends(get_storage),
):
    """Record a manual solve result and reopen the question for spaced review."""
    attempt = ReviewAttempt(attempted_at=_utcnow(), correct=payload.correct)
    updated = []

    def save_attempt(questions):
        for question in questions:
            if question.id == question_id:
                question.review_attempts.append(attempt)
                question.reviewed_at = ""
                updated.append(question)
                return True
        return False

    if not storage.update_list("questions.json", Question, save_attempt):
        raise HTTPException(status_code=404, detail="Question not found")
    return updated[0]
