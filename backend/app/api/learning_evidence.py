"""CRUD for user-entered observations about completed suggested activities."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import DATA_DIR
from app.models.schemas import LearningEvidence, LearningEvidenceCreate
from app.services.storage import StorageService
from app.services.study_agent_learning_evidence import (
    LearningEvidenceQuote,
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES,
    prepare_learning_evidence,
)

router = APIRouter(prefix="/learning-evidence", tags=["learning-evidence"])


class AgentLearningEvidenceDraftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    messages: list[str] = Field(min_length=1, max_length=MAX_MESSAGES)
    language: Literal["en", "tr"]
    evidence_claims: list[LearningEvidenceQuote] = Field(max_length=12)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if any(not item.strip() or len(item) > MAX_MESSAGE_LENGTH for item in messages):
            raise ValueError("Each student message must contain 1 to 4,000 characters.")
        return messages


class StrictLearningEvidenceCreate(LearningEvidenceCreate):
    model_config = {"extra": "forbid"}


class AgentLearningEvidenceCreateRequest(AgentLearningEvidenceDraftRequest):
    fields: StrictLearningEvidenceCreate
    evidence: dict
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}") from exc


@router.get("", response_model=list[LearningEvidence])
async def list_evidence(storage: StorageService = Depends(get_storage)):
    return storage.load_list("learning_evidence.json", LearningEvidence)


@router.post("/agent-draft")
async def learning_evidence_agent_draft(
    payload: AgentLearningEvidenceDraftRequest,
):
    prepared = prepare_learning_evidence(
        payload.messages, payload.language, [item.model_dump() for item in payload.evidence_claims],
    )
    return prepared


@router.post("/agent-create", status_code=201, response_model=LearningEvidence)
async def learning_evidence_agent_create(
    payload: AgentLearningEvidenceCreateRequest,
    storage: StorageService = Depends(get_storage),
):
    prepared = prepare_learning_evidence(
        payload.messages, payload.language, [item.model_dump() for item in payload.evidence_claims],
    )
    invalid_preview = prepared["status"] != "ready"
    field_mismatch = (
        not invalid_preview
        and (payload.fields.model_dump() != prepared["fields"]
             or payload.evidence != prepared["verified_evidence"])
    )
    digest_mismatch = not invalid_preview and not field_mismatch and payload.preview_digest != prepared["preview_digest"]

    approval_body = {
        "messages": payload.messages,
        "language": payload.language,
        "evidence_claims": [item.model_dump() for item in payload.evidence_claims],
        "fields": payload.fields.model_dump(),
        "evidence": payload.evidence,
        "preview_digest": payload.preview_digest,
    }
    fingerprint = hashlib.sha256(json.dumps(
        approval_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    approval_prefix = f"learning_evidence_agent_{payload.approval_id.hex}_"
    record_id = f"{approval_prefix}{fingerprint}"
    result: list[LearningEvidence] = []
    changed_replay = False
    invalid_request = ""

    def append_or_replay(records):
        nonlocal changed_replay, invalid_request
        prior = [item for item in records if item.id.startswith(approval_prefix)]
        if prior:
            replay = next((item for item in prior if item.id == record_id), None)
            if replay is not None and all(
                getattr(replay, field) == value for field, value in payload.fields.model_dump().items()
            ):
                result.append(replay)
                return True
            changed_replay = True
            return False
        if invalid_preview:
            invalid_request = "The learning-evidence preview is incomplete or ambiguous."
            return False
        if field_mismatch:
            invalid_request = "The approved preview does not match the verified student evidence."
            return False
        if digest_mismatch:
            invalid_request = "The learning-evidence preview changed. Review it again before saving."
            return False
        created = LearningEvidence(
            id=record_id,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            **payload.fields.model_dump(),
        )
        records.append(created)
        result.append(created)
        return True

    storage.update_list("learning_evidence.json", LearningEvidence, append_or_replay)
    if changed_replay:
        raise HTTPException(status_code=409, detail="This approval ID was already used for different learning evidence.")
    if invalid_request:
        raise HTTPException(status_code=409 if digest_mismatch else 422, detail=invalid_request)
    if not result:
        raise HTTPException(status_code=500, detail="Could not save the learning-evidence record.")
    return result[0]


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
