"""Exam CRUD with automated YKS Net and XP calculation.

Net and XP are derived on write/read through `core.formulas`, never stored,
so the JSON file only ever holds raw inputs.
"""

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import DATA_DIR
from app.models.schemas import Exam, ExamCreate, ExamDeletedApprovalLedger, ExamScoringProfile
from app.api.exam_profiles import resolve_profile
from app.services.storage import StorageError, StorageService, data_mutation_guard
from app.services.study_agent_exam import (
    EXAM_FIELDS,
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES,
    ExamQuote,
    issue_exam_state_token,
    prepare_exam_capture,
    resolve_exam_state_token,
)

router = APIRouter(prefix="/exams", tags=["exams"])
AGENT_APPROVALS_FILE = "exam_agent_approvals.json"


class AgentExamDraftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    messages: list[str] = Field(min_length=1, max_length=MAX_MESSAGES)
    language: Literal["en", "tr"]
    expected_exam_field: Literal[
        "date", "subject", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds",
    ]
    state_token: str | None = Field(default=None, max_length=24_000)
    scoring_profile_id: str = Field(min_length=1, max_length=128)
    scoring_profile_version: int = Field(ge=1)
    evidence_claims: list[ExamQuote] = Field(max_length=1)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if any(not item.strip() or len(item) > MAX_MESSAGE_LENGTH for item in messages):
            raise ValueError("Each student message must contain 1 to 4,000 characters.")
        return messages


class StrictExamCreate(ExamCreate):
    model_config = {"extra": "forbid"}


class ExamVerifiedQuote(BaseModel):
    model_config = {"extra": "forbid"}

    field: Literal[
        "date", "subject", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds",
    ]
    quote: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    message_index: int = Field(ge=0, le=MAX_MESSAGES - 1)


class AgentExamCreateRequest(AgentExamDraftRequest):
    fields: StrictExamCreate
    evidence: dict[str, dict]
    evidence_claims: list[ExamVerifiedQuote] = Field(min_length=1, max_length=len(EXAM_FIELDS))
    scoring_profile_snapshot: ExamScoringProfile
    derived: dict[str, int | float]
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID


def get_storage():
    """Dependency returning the shared JSON storage service."""
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}")


def build_exam_agent_draft(
    messages: list[str], language: str, expected_exam_field: str,
    prior_claims: list[dict], current_claims: list[dict], profile: ExamScoringProfile,
) -> dict:
    """Build one host-verified response shared by both provider adapters."""
    expected = EXAM_FIELDS[len(prior_claims)] if len(prior_claims) < len(EXAM_FIELDS) else None
    if expected != expected_exam_field:
        raise HTTPException(status_code=409, detail="The branch-exam conversation changed. Review the current question again.")
    try:
        prepared = prepare_exam_capture(messages, language, prior_claims, current_claims, profile)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="The current answer could not be verified for the expected exam field.") from exc
    if prepared["status"] != "ready":
        prepared["state_token"] = issue_exam_state_token(
            messages, language, prepared["evidence_claims"], profile.profile_id, profile.version,
        )
    else:
        prepared["state_token"] = None
    return prepared


@router.post("/agent-draft")
async def exam_agent_draft(payload: AgentExamDraftRequest, storage: StorageService = Depends(get_storage)):
    """Resolve one evidence-only answer into a non-writing branch-exam preview."""
    profile = resolve_profile(storage, payload.scoring_profile_id, payload.scoring_profile_version)
    try:
        prior_claims = resolve_exam_state_token(
            payload.state_token, payload.messages, payload.language,
            profile.profile_id, profile.version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    current_claims = [item.model_dump() for item in payload.evidence_claims]
    return build_exam_agent_draft(
        payload.messages, payload.language, payload.expected_exam_field,
        prior_claims, current_claims, profile,
    )


@router.post("/agent-create", status_code=201, response_model=Exam)
async def exam_agent_create(payload: AgentExamCreateRequest, storage: StorageService = Depends(get_storage)):
    """Recompute and atomically append only the exact approved branch-exam preview."""
    profile = resolve_profile(storage, payload.scoring_profile_id, payload.scoring_profile_version)
    if profile != payload.scoring_profile_snapshot:
        raise HTTPException(status_code=409, detail="The scoring profile changed. Review the exam preview again.")
    claims = [item.model_dump() for item in payload.evidence_claims]
    if not claims or len(claims) > len(EXAM_FIELDS):
        raise HTTPException(status_code=422, detail="Branch-exam evidence must contain at most seven verified field quotes.")
    if not claims or claims[-1]["message_index"] != len(payload.messages) - 1:
        raise HTTPException(status_code=422, detail="The final exam answer must match the newest student turn.")
    try:
        prepared = prepare_exam_capture(
            payload.messages, payload.language, claims[:-1],
            [{"field": claims[-1]["field"], "quote": claims[-1]["quote"]}], profile,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="The approved exam preview no longer matches its evidence.") from exc
    if (prepared["status"] != "ready"
            or prepared["fields"] != payload.fields.model_dump()
            or prepared["verified_evidence"] != payload.evidence
            or prepared["evidence_claims"] != claims
            or prepared["derived"] != payload.derived):
        raise HTTPException(status_code=422, detail="The approved exam preview does not match verified student evidence.")
    if prepared["preview_digest"] != payload.preview_digest:
        raise HTTPException(status_code=409, detail="The exam preview changed. Review it again before saving.")

    approval_prefix = f"exam_agent_{payload.approval_id.hex}_"
    fingerprint_body = {
        "messages": payload.messages,
        "language": payload.language,
        "expected_exam_field": payload.expected_exam_field,
        "evidence_claims": claims,
        "fields": payload.fields.model_dump(),
        "evidence": payload.evidence,
        "scoring_profile_snapshot": profile.model_dump(),
        "derived": payload.derived,
        "preview_digest": payload.preview_digest,
    }
    fingerprint = hashlib.sha256(json.dumps(
        fingerprint_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    record_id = f"{approval_prefix}{fingerprint}"
    record_fields = payload.fields.model_dump(exclude={"scoring_profile_id", "scoring_profile_version"})
    created_record = Exam(
        id=record_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        scoring_profile=profile,
        **record_fields,
    )
    result: list[Exam] = []
    conflict = ""
    ledger_model = ExamDeletedApprovalLedger
    with data_mutation_guard(storage.data_dir):
        ledger = storage.load_doc(AGENT_APPROVALS_FILE, ledger_model) or ledger_model()
        if payload.approval_id in ledger.approval_ids:
            conflict = "This approved exam was deleted and cannot be recreated by replay."
        else:
            def append_or_replay(exams):
                nonlocal conflict
                existing = next((item for item in exams if item.id.startswith(approval_prefix)), None)
                if existing is not None:
                    if (existing.id == record_id
                            and existing.model_dump(exclude={"created_at"}) == created_record.model_dump(exclude={"created_at"})):
                        result.append(existing)
                    else:
                        conflict = "This approval ID was already used for different exam data."
                    return False
                exams.append(created_record)
                result.append(created_record)
                return True

            storage.update_list("exams.json", Exam, append_or_replay)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)
    if not result:
        raise HTTPException(status_code=500, detail="Could not save the exam record.")
    return result[0]


@router.get("", response_model=list[Exam])
async def list_exams(storage: StorageService = Depends(get_storage)):
    return storage.load_list("exams.json", Exam)


@router.post("", status_code=201, response_model=Exam)
async def create_exam(payload: ExamCreate, storage: StorageService = Depends(get_storage)):
    """Create an exam from UI inputs and preserve the student's history."""
    profile = resolve_profile(storage, payload.scoring_profile_id, payload.scoring_profile_version)
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
        sections=payload.sections,
        scoring_profile=profile,
    )
    storage.append_list("exams.json", exam, Exam)
    return exam


@router.put("/{exam_id}", response_model=Exam)
async def update_exam(exam_id: str, payload: ExamCreate, storage: StorageService = Depends(get_storage)):
    updated = []

    def replace(exams):
        for index, exam in enumerate(exams):
            if exam.id == exam_id:
                data = payload.model_dump(exclude={"scoring_profile_id", "scoring_profile_version"})
                profile = exam.scoring_profile if payload.scoring_profile_id is None else resolve_profile(
                    storage, payload.scoring_profile_id, payload.scoring_profile_version,
                )
                data.update(id=exam.id, created_at=exam.created_at, scoring_profile=profile)
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
    with data_mutation_guard(storage.data_dir):
        exams = storage.load_list("exams.json", Exam)
        target = next((exam for exam in exams if exam.id == exam_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Exam not found")
        match = re.match(r"^exam_agent_([0-9a-f]{32})_[0-9a-f]{64}$", target.id)
        if match:
            approval_id = UUID(hex=match.group(1))
            ledger = storage.load_doc(AGENT_APPROVALS_FILE, ExamDeletedApprovalLedger) or ExamDeletedApprovalLedger()
            if approval_id not in ledger.approval_ids:
                ledger.approval_ids.append(approval_id)
                storage.save_doc(AGENT_APPROVALS_FILE, ledger)

        def remove_target(current):
            if target not in current:
                return False
            current.remove(target)
            return True

        if not storage.update_list("exams.json", Exam, remove_target):
            raise HTTPException(status_code=404, detail="Exam not found")
    return {"deleted": exam_id}
