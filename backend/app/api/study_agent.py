"""Optional Study Agent provider using the configured OpenAI-compatible endpoint."""

from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import DATA_DIR
from app.models.schemas import Settings
from app.api.practice import AgentDraftRequest, practice_agent_draft
from app.services.ai_service import AIService
from app.services.storage import StorageService

router = APIRouter(prefix="/study-agent", tags=["study-agent"])


class LocalStudyRequest(BaseModel):
    model_config = {"extra": "forbid"}

    consent: Literal[True]
    message: str = Field(min_length=1, max_length=4000)
    context: str = Field(max_length=6000)
    language: Literal["en", "tr"] = "en"
    endpoint: str = Field(min_length=1, max_length=2048)
    model_name: str = Field(min_length=1, max_length=256)
    has_api_key: bool
    workflow: Literal["chat", "practice-entry"] = "chat"
    messages: list[str] = Field(default_factory=list, max_length=30)


def _validate_endpoint(base_url: str) -> None:
    try:
        if base_url != base_url.strip() or any(ord(char) <= 32 or ord(char) == 127 for char in base_url):
            raise ValueError("Endpoint URL contains whitespace or control characters.")
        parsed = urlsplit(base_url)
        _ = parsed.port
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and "?" not in base_url
            and "#" not in base_url
        )
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=422, detail="Configure an absolute HTTP(S) endpoint without user information, query, or fragment.")


@router.post("/local")
async def configured_study_agent(payload: LocalStudyRequest):
    """Send an explicitly consented prompt and bounded study summary to Settings' endpoint."""
    if not payload.message.strip():
        raise HTTPException(status_code=422, detail="Enter a non-empty study question.")
    settings = StorageService(DATA_DIR).load_doc("settings.json", Settings) or Settings()
    if (
        payload.endpoint != settings.litellm_base_url
        or payload.model_name != settings.model_name
        or payload.has_api_key != bool(settings.api_key)
    ):
        raise HTTPException(status_code=409, detail="Study Agent settings changed. Review the destination and confirm consent again.")
    ai = AIService(
        base_url=settings.litellm_base_url,
        model_name=settings.model_name,
        api_key=settings.api_key,
    )
    _validate_endpoint(ai.base_url)
    try:
        if payload.workflow == "practice-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            prepared = await ai.study_practice_prepare(payload.messages, payload.language)
            draft = await practice_agent_draft(
                AgentDraftRequest(
                    messages=payload.messages,
                    language=payload.language,
                    evidence_claims=prepared["evidence_claims"],
                ),
                StorageService(DATA_DIR),
            )
            draft["proposal_mismatch"] = bool(prepared["rejected_claims"])
            return draft
        answer = await ai.study_chat(payload.message.strip(), payload.context, payload.language)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The configured Study Agent endpoint could not complete the request.") from exc
    return {"answer": answer}
