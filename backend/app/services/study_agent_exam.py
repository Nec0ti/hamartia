"""Host-verified, single-subject exam capture for the Study Agent."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.models.schemas import Exam, ExamCreate, ExamScoringProfile
from app.services.continuation_tokens import finish as finish_continuation, reserve as reserve_continuation

EXAM_FIELDS = (
    "date", "subject", "correct", "incorrect", "blank",
    "duration_minutes", "duration_seconds",
)
MAX_MESSAGES = 30
MAX_MESSAGE_LENGTH = 4000
MAX_SUBJECT_LENGTH = 120
MAX_EXAM_COUNT = 1000
MAX_EXAM_MINUTES = 24 * 60
EXAM_TOOL_NAME = "hamartia_exam_prepare"
STATE_MAX_AGE_SECONDS = 3600
STATE_SECRET = secrets.token_bytes(32)
_STATE_LOCK = threading.Lock()
_STATE_USED: dict[str, int] = {}
_STATE_PENDING: dict[str, float] = {}


class ExamQuote(BaseModel):
    """Provider hint only. Values and message indices are host-derived."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: Literal[
        "date", "subject", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds",
    ]
    quote: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if value not in EXAM_FIELDS:
            raise ValueError("Unsupported exam field.")
        return value


class ExamToolArguments(BaseModel):
    """Strict tool output; caller cannot provide parsed values or a write command."""

    model_config = ConfigDict(extra="forbid", strict=True)

    evidence: list[ExamQuote] = Field(max_length=1)


def provider_tool_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "evidence": {
                "type": "array",
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": list(EXAM_FIELDS)},
                        "quote": {"type": "string", "minLength": 1, "maxLength": MAX_MESSAGE_LENGTH},
                    },
                    "required": ["field", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["evidence"],
        "additionalProperties": False,
    }


def validate_messages(messages: list[str], language: str) -> None:
    if language not in {"en", "tr"}:
        raise ValueError("Language must be 'en' or 'tr'.")
    if not 1 <= len(messages) <= MAX_MESSAGES:
        raise ValueError(f"Provide between 1 and {MAX_MESSAGES} student messages.")
    if any(not isinstance(item, str) or not item.strip() or len(item) > MAX_MESSAGE_LENGTH for item in messages):
        raise ValueError("Each student message must contain 1 to 4,000 characters.")


def _digest(messages: list[str], language: str, profile_id: str, profile_version: int) -> str:
    encoded = json.dumps(
        {"messages": messages, "language": language, "profile_id": profile_id, "profile_version": profile_version},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode_canonical(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("Invalid canonical base64url value.")
    decoded = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    if _b64encode(decoded) != value:
        raise ValueError("Non-canonical base64url value.")
    return decoded


def issue_exam_state_token(
    messages: list[str], language: str, claims: list[dict[str, Any]],
    profile_id: str, profile_version: int,
) -> str:
    payload = {
        "v": 1,
        "scope": "branch-exam-entry",
        "issued_at": int(time.time()),
        "nonce": secrets.token_hex(16),
        "message_count": len(messages),
        "language": language,
        "transcript_digest": _digest(messages, language, profile_id, profile_version),
        "profile_id": profile_id,
        "profile_version": profile_version,
        "claims": claims,
    }
    body = _b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(STATE_SECRET, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def resolve_exam_state_token(
    token: str | None, messages: list[str], language: str,
    profile_id: str, profile_version: int, *, reserve: bool = False,
) -> list[dict[str, Any]]:
    if token is None:
        if len(messages) != 1:
            raise ValueError("Exam-capture conversation state is missing or expired.")
        return []
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode("ascii")
        signature = _b64decode_canonical(signature_text)
        if len(signature) != hashlib.sha256().digest_size:
            raise ValueError("Invalid signature length.")
        decoded = _b64decode_canonical(body_text)
        expected = hmac.new(STATE_SECRET, body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature.")
        payload = json.loads(decoded)
        issued_at, message_count = payload["issued_at"], payload["message_count"]
        if (payload["v"] != 1 or payload["scope"] != "branch-exam-entry"
                or not isinstance(issued_at, int)
                or not 0 <= time.time() - issued_at <= STATE_MAX_AGE_SECONDS
                or not isinstance(message_count, int) or len(messages) != message_count + 1
                or payload["language"] != language
                or payload["profile_id"] != profile_id or payload["profile_version"] != profile_version
                or payload["transcript_digest"] != _digest(messages[:message_count], language, profile_id, profile_version)):
            raise ValueError("The branch-exam conversation changed or expired.")
        claims = payload["claims"]
        if not isinstance(claims, list) or len(claims) >= len(EXAM_FIELDS):
            raise ValueError("Invalid branch-exam claim state.")
        for index, item in enumerate(claims):
            if (not isinstance(item, dict) or set(item) != {"field", "quote", "message_index"}
                    or item["field"] != EXAM_FIELDS[index]
                    or not isinstance(item["quote"], str)
                    or not isinstance(item["message_index"], int)
                    or not 0 <= item["message_index"] < message_count
                    or messages[item["message_index"]] != item["quote"]):
                raise ValueError("Invalid verified exam claim state.")
        reserve_continuation(_STATE_USED, _STATE_PENDING, _STATE_LOCK, token, issued_at + STATE_MAX_AGE_SECONDS)
        if not reserve:
            finish_exam_state_token(token, commit=True)
        return claims
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Exam-capture conversation state is invalid, expired, or already used.") from exc


def finish_exam_state_token(token: str | None, *, commit: bool) -> None:
    if token is not None:
        finish_continuation(_STATE_USED, _STATE_PENDING, _STATE_LOCK, token, commit=commit)


def _parse_value(field: str, quote: str) -> Any:
    value = quote.strip()
    if field == "date":
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("Enter the date as YYYY-MM-DD.")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Enter a real calendar date as YYYY-MM-DD.") from exc
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError("Enter the date as YYYY-MM-DD.")
        return value
    if field == "subject":
        if (not value or len(value) > MAX_SUBJECT_LENGTH or "\n" in value
                or any(ord(char) < 32 for char in value)):
            raise ValueError("Enter one subject name, up to 120 characters.")
        if value.casefold() in {
            "not sure", "i don't know", "i do not know", "unknown", "maybe", "perhaps",
            "bilmiyorum", "emin değilim", "emin degilim", "belki", "galiba",
        }:
            raise ValueError("The subject is uncertain or missing.")
        return value
    if re.fullmatch(r"\d{1,5}", value) is None:
        raise ValueError("Enter one non-negative whole number.")
    number = int(value)
    if field in {"correct", "incorrect", "blank"} and number > MAX_EXAM_COUNT:
        raise ValueError(f"The value must not exceed {MAX_EXAM_COUNT}.")
    if field == "duration_minutes" and number > MAX_EXAM_MINUTES:
        raise ValueError(f"The value must not exceed {MAX_EXAM_MINUTES} minutes.")
    if field == "duration_seconds" and number > 59:
        raise ValueError("Additional seconds must be from 0 to 59.")
    return number


def _questions(language: str, field: str, invalid_reason: str | None = None) -> list[str]:
    english = {
        "date": "What date was the exam? Enter the exact date as YYYY-MM-DD.",
        "subject": "What was the subject? Reply with one subject name.",
        "correct": "How many answers were correct? Reply with one whole number.",
        "incorrect": "How many answers were incorrect? Reply with one whole number.",
        "blank": "How many answers were blank? Reply with one whole number.",
        "duration_minutes": "How many whole minutes did the exam take? Enter 0 only if the recorded duration was zero.",
        "duration_seconds": "How many additional seconds did it take? Enter 0 if there were no additional seconds.",
    }
    turkish = {
        "date": "Deneme hangi tarihte yapıldı? Tam tarihi YYYY-MM-DD biçiminde yaz.",
        "subject": "Deneme hangi ders içindi? Tek bir ders adı yaz.",
        "correct": "Kaç soruyu doğru yaptın? Tek bir tam sayı yaz.",
        "incorrect": "Kaç soruyu yanlış yaptın? Tek bir tam sayı yaz.",
        "blank": "Kaç soruyu boş bıraktın? Tek bir tam sayı yaz.",
        "duration_minutes": "Deneme kaç tam dakika sürdü? Süre gerçekten sıfırsa 0 yaz.",
        "duration_seconds": "Ek olarak kaç saniye sürdü? Ek saniye yoksa 0 yaz.",
    }
    reason = invalid_reason.strip() if invalid_reason else ""
    prompt = (turkish if language == "tr" else english)[field]
    return [f"{reason} {prompt}".strip()]


def prepare_exam_capture(
    messages: list[str], language: str, prior_claims: list[dict[str, Any]],
    current_claims: list[Mapping[str, Any]], profile: ExamScoringProfile,
) -> dict[str, Any]:
    """Validate one current-turn field hint and return a non-writing preview/follow-up."""
    validate_messages(messages, language)
    if len(current_claims) > 1:
        raise ValueError("Submit at most one claim for the currently expected exam field.")
    accepted = [dict(item) for item in prior_claims]
    fields: dict[str, Any] = {"exam_type": "branch"}
    evidence: dict[str, dict[str, Any]] = {}
    previous_turn = -1
    for index, item in enumerate(accepted):
        if (set(item) != {"field", "quote", "message_index"}
                or item["field"] != EXAM_FIELDS[index]
                or not isinstance(item["message_index"], int)
                or not previous_turn < item["message_index"] < len(messages) - 1
                or not isinstance(item["quote"], str)
                or messages[item["message_index"]] != item["quote"]):
            raise ValueError("A prior exam claim does not match its original student turn.")
        previous_turn = item["message_index"]
        field = item["field"]
        fields[field] = _parse_value(field, item["quote"])
        evidence[field] = {"quote": item["quote"], "message_index": item["message_index"]}
    expected_index = len(accepted)
    expected = EXAM_FIELDS[expected_index] if expected_index < len(EXAM_FIELDS) else None
    invalid_reason = None
    rejected_claims = []
    if current_claims:
        raw = current_claims[0]
        claim = raw if isinstance(raw, ExamQuote) else ExamQuote.model_validate(raw)
        quote = claim.quote
        if expected is None or claim.field != expected or quote != messages[-1]:
            invalid_reason = "I could not verify that answer for the current field." if language == "en" else "Bu yanıtı geçerli alan için doğrulayamadım."
            rejected_claims.append({"field": claim.field, "reason": "field_or_latest_turn_mismatch"})
        else:
            try:
                value = _parse_value(expected, quote)
            except ValueError as exc:
                invalid_reason = ("That answer is not an unambiguous value." if language == "en" else "Bu yanıt tek ve açık bir değer içermiyor.")
                rejected_claims.append({"field": expected, "reason": "invalid_field_value"})
            else:
                accepted.append({"field": expected, "quote": quote, "message_index": len(messages) - 1})
                fields[expected] = value
                evidence[expected] = {"quote": quote, "message_index": len(messages) - 1}
                expected_index += 1
    missing = [field for field in EXAM_FIELDS if field not in fields]
    status = "ready" if not missing else "ambiguous" if invalid_reason else "incomplete"
    prepared_fields = None
    preview_digest = None
    derived = None
    if status == "ready":
        parsed = ExamCreate.model_validate({
            **{field: fields[field] for field in EXAM_FIELDS},
            "exam_type": "branch",
            "scoring_profile_id": profile.profile_id,
            "scoring_profile_version": profile.version,
        })
        prepared_fields = parsed.model_dump()
        exam = Exam(
            id="exam-preview", created_at="", scoring_profile=profile,
            **parsed.model_dump(exclude={"scoring_profile_id", "scoring_profile_version"}),
        )
        derived = {"net": exam.net, "xp": exam.xp}
        canonical = {
            "fields": prepared_fields,
            "evidence": evidence,
            "scoring_profile_snapshot": profile.model_dump(),
            "derived": derived,
        }
        preview_digest = hashlib.sha256(json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
    next_field = EXAM_FIELDS[len(accepted)] if len(accepted) < len(EXAM_FIELDS) else None
    question_field = expected if invalid_reason and expected else next_field
    result = {
        "status": status,
        "fields": prepared_fields or {field: fields.get(field) for field in EXAM_FIELDS} | {"exam_type": "branch"},
        "verified_evidence": evidence,
        "evidence_claims": accepted,
        "missing": missing,
        "ambiguous": {expected: [messages[-1]]} if invalid_reason and expected else {},
        "rejected_claims": rejected_claims,
        "expected_field": question_field,
        "questions": _questions(language, question_field, invalid_reason) if question_field and (missing or invalid_reason) else [],
        "scoring_profile_snapshot": profile.model_dump(),
        "derived": derived,
        "preview_digest": preview_digest,
        "write_allowed": False,
    }
    return result
