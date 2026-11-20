"""Optional Study Agent provider using the configured OpenAI-compatible endpoint."""

from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.core.config import DATA_DIR
from app.models.schemas import Settings
from app.api.practice import AgentDraftRequest, practice_agent_draft
from app.api.exams import build_exam_agent_draft, SectionedExamDraftRequest, build_sectioned_exam_agent_draft, CustomSectionedExamDraftRequest, build_custom_sectioned_exam_agent_draft
from app.api.exam_profiles import resolve_profile
from app.services.study_agent_exam import EXAM_FIELDS, resolve_exam_state_token, finish_exam_state_token
from app.api.learning_evidence import build_learning_evidence_agent_draft
from app.api.questions import build_question_agent_draft
from app.services.ai_service import AIService
from app.services.storage import StorageService
from app.services.study_agent_learning_evidence import prepare_learning_evidence, resolve_learning_evidence_state_token, finish_learning_evidence_state_token
from app.services.study_agent_question import prepare_question_capture, resolve_question_state_token, finish_question_state_token
from app.services.continuation_tokens import use as use_continuation_token

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
    workflow: Literal["chat", "practice-entry", "learning-evidence-entry", "question-entry", "exam-entry", "sectioned-exam-entry", "custom-sectioned-exam-entry"] = "chat"
    expected_evidence_field: Literal["activity", "subject", "topic", "date", "observation"] = "activity"
    state_token: str | None = Field(default=None, max_length=24_000)
    expected_question_field: Literal["question_text", "subject", "topic"] = "question_text"
    question_state_token: str | None = Field(default=None, max_length=24_000)
    expected_exam_field: Literal[
        "date", "subject", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds",
    ] = "date"
    exam_state_token: str | None = Field(default=None, max_length=24_000)
    expected_sectioned_exam_field: str = Field(default="exam_type", min_length=1, max_length=64)
    sectioned_exam_state_token: str | None = Field(default=None, max_length=24_000)
    expected_custom_exam_field: str = Field(default="format_name", min_length=1, max_length=64)
    custom_exam_state_token: str | None = Field(default=None, max_length=32_000)
    messages: list[str] = Field(default_factory=list, max_length=64)
    scoring_profile_id: str | None = None
    scoring_profile_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_profile_reference(self):
        if (self.scoring_profile_id is None) != (self.scoring_profile_version is None):
            raise ValueError("scoring profile ID and version must be provided together")
        if self.scoring_profile_id is not None and not self.scoring_profile_id.strip():
            raise ValueError("scoring profile ID is required")
        return self


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
                    scoring_profile_id=payload.scoring_profile_id,
                    scoring_profile_version=payload.scoring_profile_version,
                ),
                StorageService(DATA_DIR),
            )
            draft["proposal_mismatch"] = bool(prepared["rejected_claims"])
            return draft
        if payload.workflow == "learning-evidence-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            with use_continuation_token(payload.state_token, finish_learning_evidence_state_token):
                try:
                    prior_claims = resolve_learning_evidence_state_token(
                        payload.state_token, payload.messages, payload.language, reserve=True,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                prior = prepare_learning_evidence(payload.messages[:-1], payload.language, prior_claims) if prior_claims else None
                expected = prior["expected_field"] if prior else "activity"
                if expected != payload.expected_evidence_field:
                    raise HTTPException(status_code=409, detail="The learning-evidence conversation changed. Review the current question again.")
                prepared = await ai.study_learning_evidence_prepare(
                    payload.messages, payload.language, payload.expected_evidence_field, prior_claims,
                )
                return build_learning_evidence_agent_draft(
                    payload.messages, payload.language, payload.expected_evidence_field,
                    prior_claims, prepared["evidence_claims"],
                )
        if payload.workflow == "question-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            with use_continuation_token(payload.question_state_token, finish_question_state_token):
                try:
                    prior_claims = resolve_question_state_token(
                        payload.question_state_token, payload.messages, payload.language, reserve=True,
                    ) if payload.question_state_token is not None or len(payload.messages) > 1 else []
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                prior = prepare_question_capture(payload.messages[:-1], payload.language, prior_claims) if prior_claims else None
                expected = prior["expected_field"] if prior else "question_text"
                if expected != payload.expected_question_field:
                    raise HTTPException(status_code=409, detail="The question-capture conversation changed. Review the current question again.")
                prepared = await ai.study_question_prepare(
                    payload.messages, payload.language, expected, prior_claims,
                )
                return build_question_agent_draft(
                    payload.messages, payload.language, expected,
                    prior_claims, prepared["current_evidence_claims"],
                )
        if payload.workflow == "exam-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            if payload.scoring_profile_id is None or payload.scoring_profile_version is None:
                raise HTTPException(status_code=422, detail="Choose a scoring profile before starting exam capture.")
            exam_storage = StorageService(DATA_DIR)
            profile = resolve_profile(exam_storage, payload.scoring_profile_id, payload.scoring_profile_version)
            with use_continuation_token(payload.exam_state_token, finish_exam_state_token):
                try:
                    prior_claims = resolve_exam_state_token(
                        payload.exam_state_token, payload.messages, payload.language,
                        profile.profile_id, profile.version, reserve=True,
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                expected = EXAM_FIELDS[len(prior_claims)] if len(prior_claims) < len(EXAM_FIELDS) else None
                if expected != payload.expected_exam_field:
                    raise HTTPException(status_code=409, detail="The branch-exam conversation changed. Review the current question again.")
                prepared = await ai.study_exam_prepare(payload.messages, payload.language, expected)
                return build_exam_agent_draft(
                    payload.messages, payload.language, expected, prior_claims,
                    prepared["current_evidence_claims"], profile,
                )
        if payload.workflow == "sectioned-exam-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            if payload.scoring_profile_id is None or payload.scoring_profile_version is None:
                raise HTTPException(status_code=422, detail="Choose a scoring profile before starting exam capture.")
            sectioned_profile = resolve_profile(StorageService(DATA_DIR), payload.scoring_profile_id, payload.scoring_profile_version)
            from app.services.study_agent_sectioned_exam import resolve_state_token, finish_state_token
            with use_continuation_token(payload.sectioned_exam_state_token, finish_state_token):
                try:
                    prior_claims = resolve_state_token(payload.sectioned_exam_state_token, payload.messages, payload.language, sectioned_profile, reserve=True)
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                from app.services.study_agent_sectioned_exam import prepare_capture
                expected = prepare_capture(payload.messages, payload.language, prior_claims, [], sectioned_profile)["expected_field"]
                if expected != payload.expected_sectioned_exam_field:
                    raise HTTPException(status_code=409, detail="The sectioned exam conversation changed. Review the current question again.")
                prepared = await ai.study_sectioned_exam_prepare(payload.messages, payload.language, expected)
                return build_sectioned_exam_agent_draft(SectionedExamDraftRequest(
                    messages=payload.messages, language=payload.language, expected_exam_field=expected,
                    state_token=payload.sectioned_exam_state_token, scoring_profile_id=sectioned_profile.profile_id,
                    scoring_profile_version=sectioned_profile.version, evidence_claims=prepared["current_evidence_claims"],
                ), sectioned_profile, prior_claims)
        if payload.workflow == "custom-sectioned-exam-entry":
            if not payload.messages or any(not item.strip() or len(item) > 4000 for item in payload.messages):
                raise HTTPException(status_code=422, detail="Provide at least one student message of up to 4,000 characters.")
            if payload.scoring_profile_id is None or payload.scoring_profile_version is None:
                raise HTTPException(status_code=422, detail="Choose a scoring profile before starting exam capture.")
            custom_profile = resolve_profile(StorageService(DATA_DIR), payload.scoring_profile_id, payload.scoring_profile_version)
            from app.services.study_agent_custom_exam import prepare_capture, resolve_state_token, finish_state_token
            with use_continuation_token(payload.custom_exam_state_token, finish_state_token):
                try:
                    prior_claims = resolve_state_token(payload.custom_exam_state_token, payload.messages, payload.language, custom_profile, reserve=True)
                    expected = prepare_capture(payload.messages, payload.language, prior_claims, [], custom_profile)["expected_field"]
                except ValueError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                if expected != payload.expected_custom_exam_field:
                    raise HTTPException(status_code=409, detail="The custom exam conversation changed. Review the current question again.")
                prepared = await ai.study_custom_exam_prepare(payload.messages, payload.language, expected)
                return build_custom_sectioned_exam_agent_draft(CustomSectionedExamDraftRequest(
                    messages=payload.messages, language=payload.language, expected_exam_field=expected,
                    state_token=payload.custom_exam_state_token, scoring_profile_id=custom_profile.profile_id,
                    scoring_profile_version=custom_profile.version, evidence_claims=prepared["current_evidence_claims"],
                ), custom_profile, prior_claims)
        answer = await ai.study_chat(payload.message.strip(), payload.context, payload.language)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The configured Study Agent endpoint could not complete the request.") from exc
    return {"answer": answer}
