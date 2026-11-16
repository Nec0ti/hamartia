"""Question (Mistake Vault) endpoints.

Handles image upload, OCR text capture, council-analysis triggering, and
mistake-tagging. The AI pipeline lives in `services/ai_service`.
"""

from datetime import date, datetime
import hashlib
import ipaddress
import json
import re
from typing import Annotated, Literal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, ValidationError, field_validator
from fastapi.responses import FileResponse
from openai import OpenAIError

from app.core.config import DATA_DIR, HAMARTIA_TAGS
from app.core.study_plan import topic_priorities
from app.models.schemas import (
    MAX_QUESTION_TEXT_BYTES,
    CurriculumReference,
    Exam,
    Question,
    QuestionDeletedApprovalLedger,
    ReviewAttempt,
    Settings,
    require_utf8_byte_limit,
)
from app.services.ai_service import AIService, QuestionAnalysisPayloadTooLarge
from app.services.question_analysis_consent import question_analysis_consents
from app.services.storage import StorageError, StorageService, data_mutation_guard
from app.services.study_agent_question import (
    QuestionCaptureFields,
    QuestionQuote,
    is_unique_latest_turn_quote,
    issue_question_state_token,
    prepare_question_capture,
    resolve_question_state_token,
)
from app.services.upload_paths import UnsafeUploadPath, resolve_question_image, resolve_upload_root

router = APIRouter(prefix="/questions", tags=["questions"])
AGENT_APPROVALS_FILE = "question_agent_approvals.json"
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ANALYSIS_TAG_BYTES = 128
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def build_question_agent_draft(
    messages: list[str], language: str, expected_field: str,
    prior_claims: list[dict[str, str]], current_claims: list[dict[str, str]],
):
    """Resolve one provider turn against host state and issue the next signed state if incomplete."""
    if any(item["field"] != expected_field or not is_unique_latest_turn_quote(
            messages, item["quote"], language, expected_field,
    )
           for item in current_claims):
        raise HTTPException(status_code=422, detail="The provider quote does not match the current host-expected student turn.")
    prepared = prepare_question_capture(messages, language, [*prior_claims, *current_claims])
    if prepared["status"] != "ready":
        prepared["state_token"] = issue_question_state_token(
            messages, language, prepared["verified_evidence"],
        )
    return prepared


class AgentQuestionDraftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    messages: list[str] = Field(min_length=1, max_length=30)
    language: Literal["en", "tr"]
    expected_question_field: Literal["question_text", "subject", "topic"]
    state_token: str | None = Field(default=None, max_length=24_000)
    evidence_claims: list[QuestionQuote] = Field(max_length=1)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if any(not item.strip() or len(item) > 4000 for item in messages):
            raise ValueError("Each student message must contain 1 to 4,000 characters.")
        return messages


class StrictQuestionCaptureFields(QuestionCaptureFields):
    model_config = {"extra": "forbid"}


class QuestionEvidenceItem(BaseModel):
    model_config = {"extra": "forbid"}

    value: str = Field(max_length=MAX_QUESTION_TEXT_BYTES)
    message_index: int = Field(ge=0, le=29)
    quote: str = Field(min_length=1, max_length=MAX_QUESTION_TEXT_BYTES)
    start: int = Field(ge=0, le=4000)
    end: int = Field(ge=1, le=4000)
    skipped: bool = False


class AgentQuestionCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    messages: list[str] = Field(min_length=1, max_length=30)
    language: Literal["en", "tr"]
    evidence_claims: list[QuestionQuote] = Field(min_length=3, max_length=3)
    fields: StrictQuestionCaptureFields
    evidence: dict[Literal["question_text", "subject", "topic"], QuestionEvidenceItem]
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if any(not item.strip() or len(item) > 4000 for item in messages):
            raise ValueError("Each student message must contain 1 to 4,000 characters.")
        return messages


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
        require_utf8_byte_limit(ocr_text or "", MAX_QUESTION_TEXT_BYTES, "ocr_text")
    except ValueError as exc:
        raise HTTPException(status_code=413, detail="analysis_payload_too_large") from exc
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


@router.post("/agent-draft")
async def question_agent_draft(payload: AgentQuestionDraftRequest):
    """Validate the current expected quote and return a non-writing preview/follow-up."""
    interactive = payload.state_token is not None or len(payload.messages) > 1
    if payload.state_token is not None and len(payload.messages) < 2:
        raise HTTPException(status_code=409, detail="The question-capture conversation state is invalid or expired.")
    try:
        prior_claims = resolve_question_state_token(payload.state_token, payload.messages, payload.language) if interactive else []
        prior = prepare_question_capture(payload.messages[:-1], payload.language, prior_claims) if prior_claims else None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    expected = prior["expected_field"] if prior else "question_text"
    if expected != payload.expected_question_field:
        raise HTTPException(status_code=409, detail="The question-capture conversation changed. Review the current question again.")
    current_claims = [item.model_dump() for item in payload.evidence_claims]
    if len(current_claims) > 1:
        raise HTTPException(status_code=422, detail="Submit only the current expected field.")
    return build_question_agent_draft(payload.messages, payload.language, expected, prior_claims, current_claims)


@router.post("/agent-create", status_code=201, response_model=Question)
async def question_agent_create(payload: AgentQuestionCreateRequest, storage: StorageService = Depends(get_storage)):
    prepared = prepare_question_capture(
        payload.messages, payload.language, [item.model_dump() for item in payload.evidence_claims],
    )
    supplied_evidence = {field: item.model_dump() for field, item in payload.evidence.items()}
    invalid = prepared["status"] != "ready"
    field_mismatch = not invalid and (
        payload.fields.model_dump() != prepared["fields"]
        or supplied_evidence != prepared["verified_evidence"]
    )
    digest_mismatch = not invalid and not field_mismatch and payload.preview_digest != prepared["preview_digest"]
    approval_body = {
        "messages": payload.messages, "language": payload.language,
        "evidence_claims": [item.model_dump() for item in payload.evidence_claims],
        "fields": payload.fields.model_dump(), "evidence": supplied_evidence,
        "preview_digest": payload.preview_digest,
    }
    fingerprint = hashlib.sha256(json.dumps(
        approval_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    approval_prefix = f"q_agent_{payload.approval_id.hex}_"
    record_id = f"{approval_prefix}{fingerprint}"
    created = Question(
        id=record_id,
        ocr_text=payload.fields.question_text,
        subject=payload.fields.subject,
        topic=payload.fields.topic,
        created_at=_utcnow(),
    )
    result: list[Question] = []
    conflict = ""
    invalid_request = ""
    with data_mutation_guard(storage.data_dir):
        ledger = storage.load_doc(AGENT_APPROVALS_FILE, QuestionDeletedApprovalLedger) or QuestionDeletedApprovalLedger()
        if payload.approval_id in ledger.approval_ids:
            conflict = "This approved question was deleted and cannot be recreated by replay."
        else:
            def append_or_replay(questions):
                nonlocal conflict, invalid_request
                existing = next((item for item in questions if item.id.startswith(approval_prefix)), None)
                if existing:
                    if (existing.id == record_id and existing.ocr_text == created.ocr_text
                            and existing.subject == created.subject and existing.topic == created.topic):
                        result.append(existing)
                    else:
                        conflict = "This approval ID was already used for different question content."
                    return False
                if invalid:
                    invalid_request = "The question preview is incomplete or ambiguous."
                    return False
                if field_mismatch:
                    invalid_request = "The approved preview does not match the verified student evidence."
                    return False
                if digest_mismatch:
                    invalid_request = "The question preview changed. Review it again before saving."
                    return False
                questions.append(created)
                result.append(created)
                return True

            storage.update_list("questions.json", Question, append_or_replay)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)
    if invalid_request:
        raise HTTPException(status_code=409 if digest_mismatch else 422, detail=invalid_request)
    if not result:
        raise HTTPException(status_code=500, detail="Could not save the question record.")
    return result[0]


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


class AnalysisConsentApproval(BaseModel):
    consent_id: str


def _analysis_fingerprint(question: Question, ai: AIService, prompt: list) -> str:
    canonical = json.dumps(
        {
            "question_id": question.id,
            "created_at": question.created_at,
            "base_url": ai.base_url,
            "model_name": ai.model_name,
            "api_key": ai.api_key,
            "prompt": prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _host_class_scheme_and_authority(base_url: str) -> tuple[str, str, str]:
    parsed = urlsplit(base_url)
    hostname = parsed.hostname
    if parsed.scheme not in ("http", "https") or not hostname:
        raise HTTPException(status_code=422, detail="Configured endpoint URL is invalid")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise HTTPException(status_code=422, detail="Endpoint URLs with embedded credentials or query data cannot be reviewed safely")
    try:
        configured_port = parsed.port
        port = configured_port if configured_port is not None else (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Configured endpoint URL is invalid") from exc
    local = hostname.casefold() == "localhost" or hostname.casefold().endswith(".localhost")
    if not local:
        try:
            local = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            local = False
    safe_host = f"[{hostname}]" if ":" in hostname else hostname
    return ("local" if local else "remote", parsed.scheme, f"{safe_host}:{port}")


def _analysis_disclosure(question: Question, settings: Settings, ai: AIService, prompt: list) -> dict:
    host_class, scheme, authority = _host_class_scheme_and_authority(settings.litellm_base_url)
    raw_key = settings.api_key
    if not raw_key:
        key_setting = "blank"
    elif raw_key.casefold() == "sk-placeholder":
        key_setting = "placeholder"
    else:
        key_setting = "configured_secret"
    sent_key = "placeholder" if ai.api_key.casefold() == "sk-placeholder" else "configured_secret"
    user_content = prompt[1]["content"]
    text_item = user_content[0]
    image_included = any(item.get("type") == "image_url" for item in user_content)
    return {
        "endpoint_class": host_class,
        "endpoint_authority": authority,
        "scheme": scheme,
        "model": settings.model_name,
        "payload": {
            "analysis_instructions_included": True,
            "ocr_text_included": True,
            "ocr_text_has_content": bool(question.ocr_text),
            "image_filename_included": "Image filename:" in text_item["text"],
            "saved_image_included": image_included,
        },
        "auth_setting_category": key_setting,
        "auth_value_category": sent_key,
    }


@router.post("/{question_id}/analysis-preview")
async def preview_question_analysis(
    question_id: str,
    storage: StorageService = Depends(get_storage),
):
    """Prepare a local-only, short-lived exact-request consent summary."""
    if not question_analysis_consents.begin_preview():
        raise HTTPException(status_code=429, detail="Question analysis preview capacity is busy; try again")
    try:
        questions = storage.load_list("questions.json", Question)
        question = next((item for item in questions if item.id == question_id), None)
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")
        settings = storage.load_doc("settings.json", Settings) or Settings()
        try:
            require_utf8_byte_limit(question.ocr_text, MAX_QUESTION_TEXT_BYTES, "ocr_text")
            require_utf8_byte_limit(question.id, 512, "question_id")
            require_utf8_byte_limit(question.created_at, 128, "created_at")
            require_utf8_byte_limit(question.image_name, 1024, "image_name")
            require_utf8_byte_limit(question.image_path, 2048, "image_path")
            require_utf8_byte_limit(question.hamartia_tag, MAX_ANALYSIS_TAG_BYTES, "hamartia_tag")
            require_utf8_byte_limit(settings.litellm_base_url, 4096, "litellm_base_url")
            require_utf8_byte_limit(settings.model_name, 1024, "model_name")
            require_utf8_byte_limit(settings.api_key, 4096, "api_key")
        except ValueError as exc:
            raise HTTPException(status_code=413, detail="analysis_payload_too_large") from exc
        ai = AIService(
            base_url=settings.litellm_base_url,
            model_name=settings.model_name,
            api_key=settings.api_key,
            max_retries=0,
        )
        try:
            prompt = ai._build_prompt(question, data_dir=DATA_DIR)
        except QuestionAnalysisPayloadTooLarge as exc:
            raise HTTPException(status_code=413, detail="analysis_payload_too_large") from exc
        disclosure = _analysis_disclosure(question, settings, ai, prompt)
        try:
            snapshot = question_analysis_consents.issue(
                question=question,
                tag_at_preview=question.hamartia_tag,
                ai=ai,
                prompt=prompt,
                fingerprint=_analysis_fingerprint(question, ai, prompt),
            )
        except ValueError as exc:
            raise HTTPException(status_code=413, detail="Question analysis preview exceeds the safe memory limit") from exc
        return {"consent_id": snapshot.consent_id, **disclosure}
    finally:
        question_analysis_consents.end_preview()


@router.delete("/{question_id}/analysis-preview/{consent_id}", status_code=204)
async def cancel_question_analysis_preview(question_id: str, consent_id: str):
    """Release a dismissed local preview without contacting the configured endpoint."""
    question_analysis_consents.discard(consent_id, question_id)
    return Response(status_code=204)


@router.post("/{question_id}/analyze", response_model=Question)
async def analyze_question(
    question_id: str,
    approval: AnalysisConsentApproval,
    storage: StorageService = Depends(get_storage),
):
    """Consume explicit one-use approval and run the frozen request snapshot."""
    snapshot = question_analysis_consents.consume(approval.consent_id, question_id)
    if snapshot is None:
        raise HTTPException(status_code=409, detail="Consent expired or already used; review the request again")

    questions = storage.load_list("questions.json", Question)
    question = next((item for item in questions if item.id == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    settings = storage.load_doc("settings.json", Settings) or Settings()
    current_ai = AIService(
        base_url=settings.litellm_base_url,
        model_name=settings.model_name,
        api_key=settings.api_key,
        max_retries=0,
    )
    try:
        require_utf8_byte_limit(question.ocr_text, MAX_QUESTION_TEXT_BYTES, "ocr_text")
        require_utf8_byte_limit(question.id, 512, "question_id")
        require_utf8_byte_limit(question.created_at, 128, "created_at")
        require_utf8_byte_limit(question.image_name, 1024, "image_name")
        require_utf8_byte_limit(question.image_path, 2048, "image_path")
        require_utf8_byte_limit(settings.litellm_base_url, 4096, "litellm_base_url")
        require_utf8_byte_limit(settings.model_name, 1024, "model_name")
        require_utf8_byte_limit(settings.api_key, 4096, "api_key")
        current_prompt = current_ai._build_prompt(question, data_dir=DATA_DIR)
    except QuestionAnalysisPayloadTooLarge as exc:
        raise HTTPException(status_code=413, detail="analysis_payload_too_large") from exc
    except ValueError as exc:
        raise HTTPException(status_code=413, detail="analysis_payload_too_large") from exc
    if _analysis_fingerprint(question, current_ai, current_prompt) != snapshot.fingerprint:
        raise HTTPException(status_code=409, detail="Question or endpoint settings changed; review the request again")

    tag_at_dispatch = question.hamartia_tag
    try:
        analysis = await snapshot.ai.analyze_question(snapshot.question, prompt=snapshot.prompt)
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Yerel model isteği başarısız oldu ({type(exc).__name__}); sunucu adresi, model ve erişim ayarlarını kontrol et.",
        ) from exc
    updated = []
    stale_during_provider = False
    oversized_during_provider = False

    def save_analysis(items):
        nonlocal stale_during_provider, oversized_during_provider
        for item in items:
            if item.id == question_id:
                # update_list runs this callback while holding the data-directory
                # mutation lock and questions.json lock. Rebuild the approved
                # fingerprint inside that critical section so PATCH/settings
                # writes cannot land between the freshness check and this save.
                latest_settings = storage.load_doc("settings.json", Settings) or Settings()
                latest_ai = AIService(
                    base_url=latest_settings.litellm_base_url,
                    model_name=latest_settings.model_name,
                    api_key=latest_settings.api_key,
                    max_retries=0,
                )
                try:
                    require_utf8_byte_limit(item.ocr_text, MAX_QUESTION_TEXT_BYTES, "ocr_text")
                    require_utf8_byte_limit(item.id, 512, "question_id")
                    require_utf8_byte_limit(item.created_at, 128, "created_at")
                    require_utf8_byte_limit(item.image_name, 1024, "image_name")
                    require_utf8_byte_limit(item.image_path, 2048, "image_path")
                    require_utf8_byte_limit(latest_settings.litellm_base_url, 4096, "litellm_base_url")
                    require_utf8_byte_limit(latest_settings.model_name, 1024, "model_name")
                    require_utf8_byte_limit(latest_settings.api_key, 4096, "api_key")
                    latest_prompt = latest_ai._build_prompt(item, data_dir=DATA_DIR)
                except (QuestionAnalysisPayloadTooLarge, ValueError):
                    oversized_during_provider = True
                    return False
                if _analysis_fingerprint(item, latest_ai, latest_prompt) != snapshot.fingerprint:
                    stale_during_provider = True
                    return False
                item.analysis = analysis
                # The mistake tag is not part of the provider payload. Preserve
                # a user's edit made after preview or while the provider waited.
                if (
                    item.hamartia_tag == snapshot.tag_at_preview
                    and item.hamartia_tag == tag_at_dispatch
                ):
                    item.hamartia_tag = analysis.verdict.hamartia_tag
                updated.append(item)
                return True
        return False

    if not storage.update_list("questions.json", Question, save_analysis):
        if oversized_during_provider:
            raise HTTPException(status_code=413, detail="analysis_payload_too_large")
        if stale_during_provider:
            raise HTTPException(status_code=409, detail="Question or endpoint settings changed during analysis; review the request again")
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

    @field_validator("ocr_text")
    @classmethod
    def bound_ocr_text(cls, value: str) -> str:
        return require_utf8_byte_limit(value, MAX_QUESTION_TEXT_BYTES, "ocr_text")


def _analysis_source_fields(question: Question) -> tuple[str, str, str]:
    """Question fields used to select and label the saved prompt image/text."""
    return question.ocr_text, question.image_name, question.image_path


def _clear_stale_analysis(question: Question) -> None:
    """Drop analysis output after its source changes, retaining manual tag overrides."""
    if question.analysis is None:
        return
    generated_tag = question.analysis.verdict.hamartia_tag
    question.analysis = None
    if question.hamartia_tag == generated_tag:
        question.hamartia_tag = "[Knowledge Gap]"


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
                old_analysis_sources = _analysis_source_fields(question)
                question.subject = payload.subject.strip()
                question.topic = payload.topic.strip()
                question.ocr_text = payload.ocr_text
                if payload.curriculum_reference is not None:
                    question.curriculum_reference = payload.curriculum_reference
                if _analysis_source_fields(question) != old_analysis_sources:
                    _clear_stale_analysis(question)
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
        agent_match = re.fullmatch(r"q_agent_([0-9a-f]{32})_[0-9a-f]{64}", question_id)
        if agent_match:
            approval_id = UUID(hex=agent_match.group(1))
            ledger = storage.load_doc(AGENT_APPROVALS_FILE, QuestionDeletedApprovalLedger) or QuestionDeletedApprovalLedger()
            if approval_id not in ledger.approval_ids:
                ledger.approval_ids.append(approval_id)
                storage.save_doc(AGENT_APPROVALS_FILE, ledger)

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
