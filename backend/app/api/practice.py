"""CRUD and summaries for completed subject/topic practice sets."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import DATA_DIR
from app.core.practice import practice_topic_summaries
from app.models.schemas import PracticeSession, PracticeSessionCreate
from app.services.storage import StorageService
from app.services.study_agent_cli import EvidenceQuote, dispatch_provider_tool
from app.services.study_agent_practice import FIELDS, complete_payload, preview_digest, questions

router = APIRouter(prefix="/practice", tags=["practice"])


class AgentDraftRequest(BaseModel):
    model_config = {"extra": "forbid"}

    messages: list[str] = Field(min_length=1, max_length=30)
    language: Literal["en", "tr"]
    proposal: dict[str, str | int] | None = None
    evidence_claims: list[EvidenceQuote] | None = None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages):
        if any(not item.strip() or len(item) > 4000 for item in messages):
            raise ValueError("Each student message must contain 1 to 4,000 characters.")
        return messages

    @field_validator("proposal", mode="before")
    @classmethod
    def reject_untrusted_proposal_extras(cls, proposal):
        if proposal is None:
            return proposal
        if not isinstance(proposal, dict) or set(proposal) - set(FIELDS):
            raise ValueError("Provider proposal contains unsupported fields.")
        if any(type(value) not in {str, int} for value in proposal.values()):
            raise ValueError("Provider proposal values must be strings or integers.")
        return proposal


class StrictPracticeSessionCreate(PracticeSessionCreate):
    model_config = {"extra": "forbid"}


class AgentCreateRequest(AgentDraftRequest):
    fields: StrictPracticeSessionCreate
    evidence: dict
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_id: UUID
    duplicate_choice: Literal["new", "cancel"] | None = None


def get_storage():
    try:
        return StorageService(DATA_DIR)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Storage unavailable: {exc}") from exc


@router.get("", response_model=list[PracticeSession])
async def list_sessions(storage: StorageService = Depends(get_storage)):
    return storage.load_list("practice_sessions.json", PracticeSession)


@router.get("/insights", response_model=list[dict])
async def practice_insights(storage: StorageService = Depends(get_storage)):
    return practice_topic_summaries(storage.load_list("practice_sessions.json", PracticeSession))


@router.post("", status_code=201, response_model=PracticeSession)
async def create_session(
    payload: PracticeSessionCreate,
    storage: StorageService = Depends(get_storage),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key is not None:
        try:
            key = str(UUID(idempotency_key))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid idempotency key") from exc
        session_id = f"practice_focus_{key}"
        expected = payload.model_dump()
        result: list[PracticeSession] = []

        def append_once(sessions):
            existing = next((item for item in sessions if item.id == session_id), None)
            if existing is not None:
                if any(getattr(existing, field) != value for field, value in expected.items()):
                    raise HTTPException(status_code=409, detail="Idempotency key was already used for another practice set")
                result.append(existing)
                return True
            created = PracticeSession(
                id=session_id,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                **expected,
            )
            sessions.append(created)
            result.append(created)
            return True

        storage.update_list("practice_sessions.json", PracticeSession, append_once)
        return result[0]

    session = PracticeSession(
        id=f"practice_{uuid4().hex}",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        **payload.model_dump(),
    )
    storage.append_list("practice_sessions.json", session, PracticeSession)
    return session


@router.post("/agent-draft")
async def practice_agent_draft(payload: AgentDraftRequest, storage: StorageService = Depends(get_storage)):
    if payload.evidence_claims is not None:
        prepared = dispatch_provider_tool(
            {"evidence": [item.model_dump() for item in payload.evidence_claims]},
            messages=payload.messages,
            language=payload.language,
        )
        parsed = PracticeSessionCreate.model_validate(prepared["fields"]) if prepared["status"] == "ready" else None
        values = prepared["fields"]
        evidence = prepared["verified_evidence"]
        missing = prepared["missing"]
        ambiguous = prepared["ambiguous"]
        issues = []
        proposal_mismatch = bool(prepared["rejected_claims"])
        digest = prepared["preview_digest"]
        proposal = values
    else:
        if payload.proposal is None:
            raise HTTPException(status_code=422, detail="Provide verified evidence claims.")
        parsed, values, details = complete_payload(payload.messages)
        evidence = details["evidence"]
        missing = details["missing"]
        ambiguous = details["ambiguous"]
        issues = details.get("issues", [])
        proposal_mismatch = payload.proposal != values
        digest = preview_digest(parsed, evidence) if parsed else None
        proposal = values
    conflicts = []
    if parsed:
        conflicts = [
            item.model_dump()
            for item in storage.load_list("practice_sessions.json", PracticeSession)
            if (item.date, item.subject.casefold(), item.topic.casefold())
            == (parsed.date, parsed.subject.casefold(), parsed.topic.casefold())
        ]
    return {
        "status": prepared["status"] if payload.evidence_claims is not None else "ready" if parsed else "ambiguous" if ambiguous else "incomplete",
        "fields": parsed.model_dump() if parsed else values,
        "proposal": proposal,
        "proposal_mismatch": proposal_mismatch,
        "evidence": evidence,
        "evidence_claims": prepared["evidence_claims"] if payload.evidence_claims is not None else None,
        "missing": missing,
        "ambiguous": ambiguous,
        "questions": prepared["questions"] if payload.evidence_claims is not None else questions(payload.language, missing, ambiguous, issues),
        "preview_digest": digest,
        "conflicts": conflicts,
    }


@router.post("/agent-create", status_code=201, response_model=PracticeSession)
async def practice_agent_create(payload: AgentCreateRequest, storage: StorageService = Depends(get_storage)):
    if payload.evidence_claims is not None:
        prepared = dispatch_provider_tool(
            {"evidence": [item.model_dump() for item in payload.evidence_claims]},
            messages=payload.messages,
            language=payload.language,
        )
        parsed = PracticeSessionCreate.model_validate(prepared["fields"]) if prepared["status"] == "ready" else None
        values = prepared["fields"]
        evidence = prepared["verified_evidence"]
        digest = prepared["preview_digest"]
        claims_match = (
            not prepared["rejected_claims"]
            and [item.model_dump() for item in payload.evidence_claims] == prepared["evidence_claims"]
        )
    else:
        parsed, values, details = complete_payload(payload.messages)
        evidence = details["evidence"]
        digest = preview_digest(parsed, evidence) if parsed else None
        claims_match = True
    if not claims_match or parsed is None or values != payload.proposal or parsed.model_dump() != payload.fields.model_dump() or evidence != payload.evidence:
        raise HTTPException(status_code=422, detail="The approved preview is incomplete or no longer matches the source messages.")
    if digest != payload.preview_digest:
        raise HTTPException(status_code=409, detail="The approved preview changed. Review it again before saving.")
    created: list[PracticeSession] = []
    conflict_seen = []
    approval_prefix = f"practice_agent_{payload.approval_id.hex}_"
    approval_payload = {
        "language": payload.language,
        "messages": payload.messages,
        "proposal": payload.proposal,
        "fields": payload.fields.model_dump(),
        "evidence": payload.evidence,
        "evidence_claims": [item.model_dump() for item in payload.evidence_claims] if payload.evidence_claims is not None else None,
        "preview_digest": payload.preview_digest,
        "duplicate_choice": payload.duplicate_choice,
    }
    approval_fingerprint = hashlib.sha256(json.dumps(
        approval_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    session_id = f"{approval_prefix}{approval_fingerprint}"

    def append_with_conflict_check(sessions):
        prior_approval = [item for item in sessions if item.id.startswith(approval_prefix)]
        if prior_approval:
            replay = next((item for item in prior_approval if item.id == session_id), None)
            if replay is not None and all(
                getattr(replay, field) == value for field, value in parsed.model_dump().items()
            ):
                created.append(replay)
                return True
            conflict_seen.extend(prior_approval)
            return False
        conflicts = [
            item for item in sessions
            if (item.date, item.subject.casefold(), item.topic.casefold())
            == (parsed.date, parsed.subject.casefold(), parsed.topic.casefold())
        ]
        conflict_seen.extend(conflicts)
        if conflicts and payload.duplicate_choice != "new":
            return False
        session = PracticeSession(
            id=session_id,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            **parsed.model_dump(),
        )
        sessions.append(session)
        created.append(session)
        return True

    if not storage.update_list("practice_sessions.json", PracticeSession, append_with_conflict_check):
        raise HTTPException(status_code=409, detail={"message": "A matching practice set already exists.", "conflicts": [item.model_dump() for item in conflict_seen]})
    return created[0]


@router.put("/{session_id}", response_model=PracticeSession)
async def update_session(
    session_id: str,
    payload: PracticeSessionCreate,
    storage: StorageService = Depends(get_storage),
):
    updated = []

    def replace(sessions):
        for index, session in enumerate(sessions):
            if session.id == session_id:
                sessions[index] = PracticeSession(
                    id=session.id, created_at=session.created_at, **payload.model_dump(),
                )
                updated.append(sessions[index])
                return True
        return False

    if not storage.update_list("practice_sessions.json", PracticeSession, replace):
        raise HTTPException(status_code=404, detail="Practice set not found")
    return updated[0]


@router.delete("/{session_id}")
async def delete_session(session_id: str, storage: StorageService = Depends(get_storage)):
    def remove(sessions):
        remaining = [item for item in sessions if item.id != session_id]
        if len(remaining) == len(sessions):
            return False
        sessions[:] = remaining
        return True

    if not storage.update_list("practice_sessions.json", PracticeSession, remove):
        raise HTTPException(status_code=404, detail="Practice set not found")
    return {"deleted": session_id}
