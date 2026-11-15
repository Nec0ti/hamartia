"""Question (Mistake Vault) endpoints.

Handles image upload, OCR text capture, council-analysis triggering, and
mistake-tagging. The AI pipeline lives in `services/ai_service`.
"""

from datetime import date, datetime
import json
from typing import Annotated
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError
from fastapi.responses import FileResponse
from openai import OpenAIError

from app.core.config import DATA_DIR, HAMARTIA_TAGS
from app.core.study_plan import topic_priorities
from app.models.schemas import CurriculumReference, Exam, Question, ReviewAttempt
from app.services.ai_service import AIService, get_ai
from app.services.storage import StorageError, StorageService, data_mutation_guard
from app.services.upload_paths import UnsafeUploadPath, resolve_question_image, resolve_upload_root

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
    file: UploadFile | None = File(default=None),
    ocr_text: str = Form(""),
    subject: str = Form(""),
    topic: str = Form(""),
    storage: StorageService = Depends(get_storage),
    exam_id: Annotated[str, Form()] = "",
    question_number: Annotated[int | None, Form(ge=1)] = None,
    solve_order: Annotated[int | None, Form(ge=1)] = None,
    time_spent_seconds: Annotated[int | None, Form(ge=1)] = None,
    curriculum_reference_json: Annotated[str, Form()] = "{}",
):
    """Store an uploaded question image, OCR text, and study labels."""
    exam_id = exam_id.strip()
    if not exam_id and any(value is not None for value in (question_number, solve_order, time_spent_seconds)):
        raise HTTPException(status_code=422, detail="Exam details are required for question order metadata")
    if len(curriculum_reference_json) > 4096:
        raise HTTPException(status_code=422, detail="Curriculum reference is too large")
    try:
        reference_data = json.loads(curriculum_reference_json)
        if not isinstance(reference_data, dict):
            raise ValueError("Curriculum reference must be an object")
        curriculum_reference = CurriculumReference.model_validate(reference_data)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Curriculum reference fields are invalid") from exc

    safe_name = ""
    path = None
    contents = None
    if file:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        ext = Path(file.filename).suffix.lower()
        if ext not in IMAGE_TYPES or file.content_type not in (None, "", IMAGE_TYPES[ext]):
            raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP image")
        safe_name = f"q_{uuid4().hex}{ext}"

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
    elif not (ocr_text or "").strip():
        raise HTTPException(status_code=422, detail="Add an image or question text")

    with data_mutation_guard(DATA_DIR):
        try:
            exam_section_total = None
            if exam_id:
                exams = storage.load_list("exams.json", Exam)
                exam = next((item for item in exams if item.id == exam_id), None)
                if exam is None:
                    raise HTTPException(status_code=404, detail="Exam not found")
                total_questions = exam.correct + exam.incorrect + exam.blank
                if exam.sections:
                    section = next((
                        item for item in exam.sections
                        if item.subject.casefold() == subject.strip().casefold()
                    ), None)
                    if section is None:
                        raise HTTPException(status_code=422, detail="Choose a subject section from this mock exam")
                    total_questions = section.correct + section.incorrect + section.blank
                    if total_questions == 0:
                        raise HTTPException(status_code=422, detail="Cannot link a question to an empty exam section")
                    exam_section_total = total_questions
                    size_label = "selected section size"
                else:
                    size_label = "exam size"
                if any(value is not None and value > total_questions for value in (question_number, solve_order)):
                    raise HTTPException(status_code=422, detail=f"Question number and solve order cannot exceed the {size_label}")

            question = Question(
                id=f"q_{uuid4().hex}",
                image_name=safe_name,
                image_path=(Path("uploads") / safe_name).as_posix() if safe_name else "",
                ocr_text=ocr_text or "",
                subject=subject.strip(),
                topic=topic.strip(),
                curriculum_reference=curriculum_reference,
                created_at=_utcnow(),
                exam_id=exam_id,
                question_number=question_number,
                solve_order=solve_order,
                time_spent_seconds=time_spent_seconds,
                exam_section_total=exam_section_total,
            )
            if safe_name:
                try:
                    path = resolve_upload_root(DATA_DIR, create=True) / safe_name
                except UnsafeUploadPath as exc:
                    raise HTTPException(status_code=500, detail=str(exc)) from exc
                with path.open("xb") as image_file:
                    image_file.write(contents)
            storage.append_list("questions.json", question, Question)
        except OSError as exc:
            if path:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise HTTPException(status_code=500, detail=f"Could not save upload: {exc}") from exc
        except Exception:
            if path:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
    return question


@router.get("", response_model=list[Question])
async def list_questions(storage: StorageService = Depends(get_storage)):
    return storage.load_list("questions.json", Question)


@router.get("/insights", response_model=dict)
async def question_insights(
    storage: StorageService = Depends(get_storage),
    today: date | None = None,
):
    """Rank repeated mistake topics without calling a model."""
    questions = storage.load_list("questions.json", Question)
    exams = storage.load_list("exams.json", Exam)
    return topic_priorities(questions, today=today, exams=exams)


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

    try:
        path = resolve_question_image(DATA_DIR, question.image_path)
    except UnsafeUploadPath:
        raise HTTPException(status_code=404, detail="Question image not found")
    if not path.is_file():
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

    try:
        analysis = await ai.analyze_question(question)
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Yerel model isteği başarısız oldu ({type(exc).__name__}); sunucu adresi, model ve erişim ayarlarını kontrol et.",
        ) from exc
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
    attempt_day: date | None = None


class QuestionUpdate(BaseModel):
    subject: str
    topic: str
    ocr_text: str
    # Omitted/null preserves the saved reference; send {} to clear it.
    curriculum_reference: CurriculumReference | None = None


@router.patch("/{question_id}", response_model=Question)
async def update_question(
    question_id: str,
    payload: QuestionUpdate,
    storage: StorageService = Depends(get_storage),
):
    updated = []

    def edit(questions):
        for question in questions:
            if question.id == question_id:
                if not question.image_path and not payload.ocr_text.strip():
                    raise HTTPException(status_code=422, detail="A text-only question must keep question text")
                question.subject = payload.subject.strip()
                question.topic = payload.topic.strip()
                question.ocr_text = payload.ocr_text
                if payload.curriculum_reference is not None:
                    question.curriculum_reference = payload.curriculum_reference
                updated.append(question)
                return True
        return False

    if not storage.update_list("questions.json", Question, edit):
        raise HTTPException(status_code=404, detail="Question not found")
    return updated[0]


@router.delete("/{question_id}", status_code=200)
async def delete_question(question_id: str, storage: StorageService = Depends(get_storage)):
    deleted = []
    image_path = None

    with data_mutation_guard(DATA_DIR):
        def remove(questions):
            nonlocal image_path
            for index, question in enumerate(questions):
                if question.id == question_id:
                    if question.image_path:
                        try:
                            resolve_upload_root(DATA_DIR)
                        except UnsafeUploadPath as exc:
                            raise HTTPException(status_code=500, detail=str(exc)) from exc
                        try:
                            image_path = resolve_question_image(DATA_DIR, question.image_path)
                        except UnsafeUploadPath:
                            image_path = None
                    deleted.append(questions.pop(index))
                    return True
            return False

        if not storage.update_list("questions.json", Question, remove):
            raise HTTPException(status_code=404, detail="Question not found")

        # shortcut: JSON and file deletion cannot share a transaction; use transactional blob storage for crash-proof cleanup.
        if image_path and image_path.is_file():
            try:
                image_path.unlink()
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Question deleted but its image could not be removed: {exc}") from exc
    return {"deleted": question_id}


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
    attempted_at = _utcnow()
    # Older API clients that omit the user's calendar date keep a deterministic UTC fallback.
    attempt_day = payload.attempt_day or datetime.fromisoformat(attempted_at.replace("Z", "+00:00")).date()
    attempt = ReviewAttempt(
        attempted_at=attempted_at, correct=payload.correct, attempt_day=attempt_day.isoformat(),
    )
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
