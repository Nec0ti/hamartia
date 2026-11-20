"""Host-verified conversational capture for user-defined sectioned mock exams."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models.schemas import Exam, ExamCreate, ExamScoringProfile
from app.services.continuation_tokens import finish as finish_continuation, reserve as reserve_continuation
MAX_MESSAGE_LENGTH = 4000
MAX_MESSAGES = 64
MAX_TRANSCRIPT_CHARACTERS = 32_000
MAX_SUBJECT_LENGTH = 120

MAX_SECTIONS = 12
MAX_COUNT = 1000
MAX_MINUTES = 24 * 60
TOOL_NAME = "hamartia_custom_exam_prepare"
STATIC_FIELDS = ("format_name", "date", "duration_minutes", "duration_seconds", "section_count")
SECTION_FIELDS = ("subject", "correct", "incorrect", "blank")
STATE_SECRET = secrets.token_bytes(32)
STATE_LOCK = threading.Lock()
STATE_USED: dict[str, int] = {}
STATE_PENDING: dict[str, tuple[float, object | None]] = {}


class SectionedExamQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class SectionedExamToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence: list[SectionedExamQuote] = Field(max_length=1)


def provider_tool_parameters() -> dict[str, Any]:
    return {"type": "object", "properties": {"evidence": {"type": "array", "maxItems": 1, "items": {
        "type": "object", "properties": {"field": {"type": "string", "maxLength": 64}, "quote": {"type": "string", "minLength": 1, "maxLength": MAX_MESSAGE_LENGTH}},
        "required": ["field", "quote"], "additionalProperties": False,
    }}}, "required": ["evidence"], "additionalProperties": False}


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if re.fullmatch(r"[A-Za-z0-9_-]+", value or "") is None:
        raise ValueError("Invalid state encoding.")
    decoded = base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
    if _encode(decoded) != value:
        raise ValueError("Non-canonical state encoding.")
    return decoded


def _digest(messages: list[str], language: str, profile: ExamScoringProfile) -> str:
    data = json.dumps({"messages": messages, "language": language, "profile": profile.model_dump()}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def issue_state_token(messages: list[str], language: str, claims: list[dict], profile: ExamScoringProfile) -> str:
    payload = {"v": 1, "scope": "custom-sectioned", "issued_at": int(time.time()), "nonce": secrets.token_hex(16),
        "message_count": len(messages), "language": language, "transcript_digest": _digest(messages, language, profile),
        "profile_id": profile.profile_id, "profile_version": profile.version, "claims": claims}
    body = _encode(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())
    return body + "." + _encode(hmac.new(STATE_SECRET, body.encode(), hashlib.sha256).digest())


def resolve_state_token(token: str | None, messages: list[str], language: str, profile: ExamScoringProfile, *, reserve: bool = False) -> list[dict]:
    if token is None:
        if len(messages) != 1:
            raise ValueError("Sectioned exam conversation state is missing or expired.")
        return []
    try:
        body, signature = token.split(".", 1)
        if not hmac.compare_digest(_decode(signature), hmac.new(STATE_SECRET, body.encode("ascii"), hashlib.sha256).digest()):
            raise ValueError("Invalid signature.")
        payload = json.loads(_decode(body))
        count = payload["message_count"]
        if (payload["v"] != 1 or payload["scope"] != "custom-sectioned" or not isinstance(count, int)
                or len(messages) != count + 1 or payload["language"] != language
                or payload["transcript_digest"] != _digest(messages[:count], language, profile)
                or payload["profile_id"] != profile.profile_id or payload["profile_version"] != profile.version
                or not isinstance(payload["issued_at"], int) or not 0 <= time.time() - payload["issued_at"] <= 3600):
            raise ValueError("Conversation changed or expired.")
        claims = payload["claims"]
        claim_fields = expected_fields(claims)
        if not isinstance(claims, list) or len(claims) > len(STATIC_FIELDS) + MAX_SECTIONS * len(SECTION_FIELDS):
            raise ValueError("Invalid claim count.")
        previous = -1
        for i, claim in enumerate(claims):
            if (not isinstance(claim, dict) or set(claim) != {"field", "quote", "message_index"}
                    or i >= len(claim_fields) or claim["field"] != claim_fields[i]
                    or not isinstance(claim["message_index"], int) or not previous < claim["message_index"] < count
                    or not isinstance(claim["quote"], str) or messages[claim["message_index"]] != claim["quote"]):
                raise ValueError("Invalid verified claims.")
            previous = claim["message_index"]
        reserve_continuation(STATE_USED, STATE_PENDING, STATE_LOCK, token, payload["issued_at"] + 3600)
        if not reserve:
            finish_state_token(token, commit=True)
        return claims
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Sectioned exam conversation state is invalid, expired, or already used.") from exc


def finish_state_token(token: str | None, *, commit: bool) -> None:
    if token is not None:
        finish_continuation(STATE_USED, STATE_PENDING, STATE_LOCK, token, commit=commit)


def expected_fields(claims: list[dict]) -> list[str]:
    fields = list(STATIC_FIELDS)
    if len(claims) >= len(STATIC_FIELDS):
        try:
            count = int(claims[4]["quote"].strip())
        except (KeyError, TypeError, ValueError, IndexError):
            count = 0
        if 1 <= count <= MAX_SECTIONS:
            fields.extend(f"section_{index}_{name}" for index in range(1, count + 1) for name in SECTION_FIELDS)
    return fields


def _value(field: str, quote: str) -> Any:
    value = quote.strip()
    if field == "format_name" or field.endswith("_subject"):
        if re.match(r"(?i)^(?:maybe\b|perhaps\b|possibly\b|not sure\b|i think\b|might be\b|belki\b|galiba\b|emin değilim\b|emin degilim\b)", value):
            raise ValueError("The name is uncertain.")
    if field == "format_name":
        if not value or len(value) > 120 or "\n" in value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter one custom mock name, up to 120 characters.")
        return value
    if field == "date":
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("Enter the exact date as YYYY-MM-DD.")
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError("Enter a real date as YYYY-MM-DD.")
        return value
    if field.endswith("_subject"):
        if not value or len(value) > MAX_SUBJECT_LENGTH or "\n" in value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter one section name, up to 120 characters.")
        if value.casefold() in {"unknown", "maybe", "perhaps", "not sure", "i don't know", "i do not know", "bilmiyorum", "belki", "galiba", "emin değilim", "emin degilim"}:
            raise ValueError("Subject is missing or uncertain.")
        return value
    if re.fullmatch(r"\d{1,5}", value) is None:
        raise ValueError("Enter one non-negative whole number.")
    number = int(value)
    if field == "section_count" and not 1 <= number <= MAX_SECTIONS:
        raise ValueError(f"Enter a section count from 1 to {MAX_SECTIONS}.")
    if field.endswith(("_correct", "_incorrect", "_blank")) and number > MAX_COUNT:
        raise ValueError(f"Each count must not exceed {MAX_COUNT}.")
    if field == "duration_minutes" and number > MAX_MINUTES:
        raise ValueError(f"Duration must not exceed {MAX_MINUTES} minutes.")
    if field == "duration_seconds" and number > 59:
        raise ValueError("Additional seconds must be from 0 to 59.")
    return number


def _question(field: str, language: str) -> str:
    label = field.replace("section_", "section ").replace("_", " ")
    is_section_data = re.fullmatch(r"section_(?:[1-9]|1[0-2])_(subject|correct|incorrect|blank)", field) is not None
    if language == "tr":
        match = re.fullmatch(r"section_(\d+)_(subject|correct|incorrect|blank)", field)
        if match:
            number, name = match.groups()
            label = f"{number}. bölüm " + {"subject": "dersi", "correct": "doğru sayısı", "incorrect": "yanlış sayısı", "blank": "boş sayısı"}[name]
        names = {"format_name": "denemenin kendi adı", "date": "tarih (YYYY-MM-DD)", "duration_minutes": "tam dakika", "duration_seconds": "ek saniye", "section_count": f"bölüm sayısı (1-{MAX_SECTIONS})"}
        return f"{label if is_section_data else names[field]} için tek ve açık bir değer yaz."
    names = {"format_name": "your own mock name", "date": "date (YYYY-MM-DD)", "duration_minutes": "whole minutes", "duration_seconds": "additional seconds", "section_count": f"section count (1-{MAX_SECTIONS})"}
    return f"Reply with one clear value for {label if is_section_data else names[field]}."


def prepare_capture(messages: list[str], language: str, prior: list[dict], current: list[Mapping[str, Any]], profile: ExamScoringProfile) -> dict:
    if language not in {"en", "tr"} or not 1 <= len(messages) <= MAX_MESSAGES or any(
        not isinstance(item, str) or not item.strip() or len(item) > MAX_MESSAGE_LENGTH for item in messages
    ) or sum(len(item) for item in messages) > MAX_TRANSCRIPT_CHARACTERS:
        raise ValueError(f"messages must contain 1 to {MAX_MESSAGES} student messages, up to 4,000 characters each and 32,000 characters total")
    if len(current) > 1:
        raise ValueError("Submit one quote at a time.")
    claims = [dict(item) for item in prior]
    fields: dict[str, Any] = {}
    evidence: dict[str, dict] = {}
    expected_list = expected_fields(claims)
    previous_turn = -1
    for index, item in enumerate(claims):
        if (set(item) != {"field", "quote", "message_index"} or index >= len(expected_list)
                or item["field"] != expected_list[index] or not isinstance(item["message_index"], int)
                or not previous_turn < item["message_index"] < len(messages) - 1
                or not isinstance(item["quote"], str) or messages[item["message_index"]] != item["quote"]):
            raise ValueError("Prior sectioned exam claims do not match the transcript.")
        previous_turn = item["message_index"]
        fields[item["field"]] = _value(item["field"], item["quote"])
        evidence[item["field"]] = {"quote": item["quote"], "message_index": item["message_index"]}
    expected = expected_list[len(claims)] if len(claims) < len(expected_list) else None
    issue = False
    rejected = []
    if current:
        claim = current[0] if isinstance(current[0], SectionedExamQuote) else SectionedExamQuote.model_validate(current[0])
        if claim.field != expected or claim.quote != messages[-1]:
            issue = True
            rejected.append({"reason": "field_or_latest_turn_mismatch"})
        else:
            try:
                value = _value(expected, claim.quote)
                if expected.endswith("_subject") and value.casefold() in {
                    fields[f"section_{number}_subject"].casefold()
                    for number in range(1, int(fields["section_count"]))
                    if f"section_{number}_subject" in fields
                }:
                    raise ValueError("A section subject must be unique.")
            except ValueError:
                issue = True
                rejected.append({"reason": "invalid_field_value"})
            else:
                claims.append({"field": expected, "quote": claim.quote, "message_index": len(messages) - 1})
                fields[expected] = value
                evidence[expected] = {"quote": claim.quote, "message_index": len(messages) - 1}
    expected_list = expected_fields(claims)
    missing = expected_list[len(claims):]
    status = "ambiguous" if issue else "incomplete" if missing else "ready"
    prepared_fields = derived = preview_digest = None
    if status == "ready":
        count = fields["section_count"]
        sections = [{"subject": fields[f"section_{i}_subject"], **{key: fields[f"section_{i}_{key}"] for key in ("correct", "incorrect", "blank")}} for i in range(1, count + 1)]
        parsed = ExamCreate.model_validate({"date": fields["date"], "exam_type": "custom", "format_name": fields["format_name"], "subject": fields["format_name"], "correct": 0, "incorrect": 0, "blank": 0, "duration_minutes": fields["duration_minutes"], "duration_seconds": fields["duration_seconds"], "sections": sections, "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version})
        prepared_fields = parsed.model_dump()
        exam = Exam(id="exam-preview", date=parsed.date, exam_type=parsed.exam_type, format_name=parsed.format_name, subject=parsed.subject, correct=parsed.correct, incorrect=parsed.incorrect, blank=parsed.blank, duration_minutes=parsed.duration_minutes, duration_seconds=parsed.duration_seconds, sections=parsed.sections, scoring_profile=profile)
        derived = {"net": exam.net, "xp": exam.xp}
        canonical = {"fields": prepared_fields, "evidence": evidence, "scoring_profile_snapshot": profile.model_dump(), "derived": derived}
        preview_digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    next_field = expected_fields(claims)[len(claims)] if len(claims) < len(expected_fields(claims)) else None
    asked_field = expected if issue else next_field
    partial = {**fields, "sections": [{"subject": fields.get(f"section_{i}_subject"), **{key: fields.get(f"section_{i}_{key}") for key in ("correct", "incorrect", "blank")}} for i in range(1, fields.get("section_count", 0) + 1)]}
    return {"status": status, "fields": prepared_fields or partial, "verified_evidence": evidence, "evidence_claims": claims,
        "missing": missing, "ambiguous": {expected: [messages[-1]]} if issue and expected else {}, "rejected_claims": rejected,
        "expected_field": asked_field, "questions": [_question(asked_field, language)] if asked_field else [],
        "scoring_profile_snapshot": profile.model_dump(), "derived": derived, "preview_digest": preview_digest, "write_allowed": False}
