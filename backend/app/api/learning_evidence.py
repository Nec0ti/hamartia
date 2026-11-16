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
from app.models.schemas import LearningEvidence, LearningEvidenceCreate, LearningEvidenceDeletedApprovalLedger
from app.services.storage import StorageService, data_mutation_guard
from app.services.study_agent_learning_evidence import (
    LearningEvidenceQuote,
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES,
    prepare_learning_evidence,
)

router = APIRouter(prefix="/learning-evidence", tags=["learning-evidence"])
AGENT_APPROVALS_FILE = "learning_evidence_agent_approvals.json"


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
    approval_key = payload.approval_id
    created = LearningEvidence(
        id=record_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **payload.fields.model_dump(),
    )
    result: list[LearningEvidence] = []
    conflict = ""
    invalid_request = ""

    # Serialize the approval lookup and record mutation together with deletes.
    # The deletion ledger stores only a random approval UUID after a user has
    # deleted an entry; it never stores a transcript hash or result ID.
    with data_mutation_guard(storage.data_dir):
        ledger = storage.load_doc(AGENT_APPROVALS_FILE, LearningEvidenceDeletedApprovalLedger) or LearningEvidenceDeletedApprovalLedger()
        if approval_key in ledger.approval_ids:
            conflict = "This approved learning-evidence record was deleted and cannot be recreated by replay."
        else:
            def append_or_replay(records):
                nonlocal conflict, invalid_request
                existing = next((item for item in records if item.id.startswith(approval_prefix)), None)
                if existing is not None:
                    if existing.id == record_id and all(
                        getattr(existing, field) == value for field, value in payload.fields.model_dump().items()
                    ):
                        result.append(existing)
                    else:
                        conflict = "This approval ID was already used for different learning evidence."
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
                records.append(created)
                result.append(created)
                return True

            storage.update_list("learning_evidence.json", LearningEvidence, append_or_replay)

    if conflict:
        raise HTTPException(status_code=409, detail=conflict)
    if invalid_request:
        status_code = 409 if digest_mismatch else 422
        raise HTTPException(status_code=status_code, detail=invalid_request)
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
    with data_mutation_guard(storage.data_dir):
        records = storage.load_list("learning_evidence.json", LearningEvidence)
        target = next((record for record in records if record.id == evidence_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="Learning evidence not found")
        approval_id = None
        parts = target.id.split("_")
        if len(parts) == 5 and parts[:3] == ["learning", "evidence", "agent"]:
            try:
                approval_id = UUID(hex=parts[3])
            except ValueError:
                approval_id = None
        if approval_id is not None:
            ledger = storage.load_doc(AGENT_APPROVALS_FILE, LearningEvidenceDeletedApprovalLedger) or LearningEvidenceDeletedApprovalLedger()
            if approval_id not in ledger.approval_ids:
                ledger.approval_ids.append(approval_id)
                storage.save_doc(AGENT_APPROVALS_FILE, ledger)
        def remove_target(current):
            if target not in current:
                return False
            current.remove(target)
            return True

        if not storage.update_list("learning_evidence.json", LearningEvidence, remove_target):
            raise HTTPException(status_code=404, detail="Learning evidence not found")
    return {"deleted": evidence_id}
