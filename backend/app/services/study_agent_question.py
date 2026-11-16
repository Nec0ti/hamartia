"""Host-verified, text-only Study Agent capture for missed-question records."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import binascii
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.schemas import MAX_QUESTION_TEXT_BYTES, require_utf8_byte_limit

QUESTION_TOOL_NAME = "hamartia_question_prepare"
QUESTION_FIELDS = ("question_text", "subject", "topic")
QUESTION_FIELD_LIMITS = {"question_text": MAX_QUESTION_TEXT_BYTES, "subject": 120, "topic": 160}
MAX_MESSAGES = 30
MAX_MESSAGE_LENGTH = 4000
QUESTION_STATE_MAX_AGE_SECONDS = 3600
_QUESTION_STATE_SECRET = secrets.token_bytes(32)
_QUESTION_STATE_USED: dict[str, int] = {}
_QUESTION_STATE_LOCK = threading.Lock()


class QuestionQuote(BaseModel):
    """An untrusted field/quote hint. Values are always resolved by the host."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: Literal["question_text", "subject", "topic"]
    quote: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class QuestionToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence: list[QuestionQuote] = Field(max_length=1)


class QuestionCaptureFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    subject: str = Field(default="", max_length=120)
    topic: str = Field(default="", max_length=160)


def provider_tool_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"evidence": {
            "type": "array", "maxItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(QUESTION_FIELDS)},
                    "quote": {"type": "string", "minLength": 1, "maxLength": MAX_MESSAGE_LENGTH},
                },
                "required": ["field", "quote"], "additionalProperties": False,
            },
        }},
        "required": ["evidence"], "additionalProperties": False,
    }


def _validate_messages(messages: list[str], language: str) -> None:
    if language not in {"en", "tr"}:
        raise ValueError("language must be en or tr")
    if not 1 <= len(messages) <= MAX_MESSAGES or any(
        not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE_LENGTH
        for message in messages
    ):
        raise ValueError("messages must contain 1 to 30 non-empty student messages of up to 4,000 characters")


def _occurrences(message: str, quote: str) -> list[tuple[int, int]]:
    found = []
    start = message.find(quote)
    while start >= 0:
        found.append((start, start + len(quote)))
        start = message.find(quote, start + 1)
    return found


def is_unique_latest_turn_quote(messages: list[str], quote: str, language: str, field: str) -> bool:
    """Bind provider hints to the newest whole turn; repeated optional skips are safe by field order."""
    if not messages or quote != messages[-1]:
        return False
    if field in {"subject", "topic"} and _is_skip(quote, language):
        return True
    return sum(len(_occurrences(message, quote)) for message in messages) == 1


_META_INTENT = re.compile(
    r"(?i)^(?:maybe\s+i\s+(?:will|might|may)|i\s+(?:will|might|may|plan\s+to|intend\s+to)|"
    r"if\s+i\s+.{0,80}\s+i\s+(?:would|could)|(?:don't|do\s+not|won't|will\s+not)\s+"
    r"(?:save|add|paste|send|record)|kaydetme|ekleme|belki\s+(?:daha\s+sonra\s+)?"
    r"(?:ekleyeceğim|ekleyecegim|eklerim|kaydedeceğim|kaydedecegim|kaydederim)|(?:sonra|daha\s+sonra)\s+"
    r"(?:ekleyeceğim|ekleyecegim|kaydedeceğim|kaydedecegim)|"
    r"eğer\s+.{0,80}\s+(?:eklerim|kaydedebilirim))\b"
)
_UNCERTAIN_LABEL = re.compile(r"(?i)^(?:maybe\b|perhaps\b|possibly\b|not sure\b|i think\b|might be\b|belki\b|emin değilim\b|emin degilim\b|sanırım\b|sanirim\b|galiba\b)")

_SKIP = {
    "en": {"skip", "none", "leave blank", "not provided", "i don't know", "unknown"},
    "tr": {"atla", "boş bırak", "bos birak", "belirtme", "bilmiyorum", "yok"},
}


def _normalise_choice(value: str) -> str:
    return re.sub(r"[.!?؟]+$", "", value.strip()).casefold()


def _is_skip(value: str, language: str) -> bool:
    return _normalise_choice(value) in _SKIP[language]


def _transcript_digest(messages: list[str], language: str) -> str:
    encoded = json.dumps({"messages": messages, "language": language}, ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def issue_question_state_token(messages: list[str], language: str, verified_evidence: dict) -> str:
    payload = {
        "v": 1, "issued_at": int(time.time()), "nonce": secrets.token_urlsafe(12),
        "message_count": len(messages), "transcript_digest": _transcript_digest(messages, language),
        "language": language,
        "claims": [{"field": field, "quote": evidence["quote"]} for field, evidence in verified_evidence.items()],
    }
    body = urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":")).encode("utf-8")).rstrip(b"=")
    signature = hmac.new(_QUESTION_STATE_SECRET, body, hashlib.sha256).digest()
    return f"{body.decode('ascii')}.{urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def resolve_question_state_token(token: str | None, messages: list[str], language: str) -> list[dict[str, str]]:
    if token is None:
        if len(messages) != 1:
            raise ValueError("A host-issued question-capture state token is required to continue this conversation.")
        return []
    if not isinstance(token, str) or len(token) > 24_000 or token.count(".") != 1:
        raise ValueError("Question-capture conversation state is invalid or expired.")
    body_text, signature_text = token.split(".", 1)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", body_text) or not re.fullmatch(r"[A-Za-z0-9_-]+", signature_text):
            raise ValueError
        body = body_text.encode("ascii")
        decoded = urlsafe_b64decode(body_text + "=" * (-len(body_text) % 4))
        signature = urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        if (len(signature) != hashlib.sha256().digest_size
                or urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != body_text
                or urlsafe_b64encode(signature).rstrip(b"=").decode("ascii") != signature_text):
            raise ValueError
        expected = hmac.new(_QUESTION_STATE_SECRET, body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(decoded)
        issued_at, count = payload["issued_at"], payload["message_count"]
        if (payload["v"] != 1 or not isinstance(issued_at, int)
                or not 0 <= time.time() - issued_at <= QUESTION_STATE_MAX_AGE_SECONDS
                or not isinstance(count, int) or count < 1 or len(messages) != count + 1
                or payload["language"] != language
                or payload["transcript_digest"] != _transcript_digest(messages[:count], language)):
            raise ValueError
        claims = [QuestionQuote.model_validate(item).model_dump() for item in payload["claims"]]
        if len(claims) > len(QUESTION_FIELDS):
            raise ValueError
        canonical = f"{body_text}.{signature_text}".encode("ascii")
        replay_key = hashlib.sha256(canonical).hexdigest()
        now = int(time.time())
        with _QUESTION_STATE_LOCK:
            for key, used_at in list(_QUESTION_STATE_USED.items()):
                if now - used_at > QUESTION_STATE_MAX_AGE_SECONDS:
                    _QUESTION_STATE_USED.pop(key, None)
            if replay_key in _QUESTION_STATE_USED or len(_QUESTION_STATE_USED) >= 4096:
                raise ValueError
            _QUESTION_STATE_USED[replay_key] = now
        return claims
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Question-capture conversation state is invalid or expired.") from exc


def _questions(language: str, field: str) -> list[str]:
    questions = {
        "question_text": (
            "Paste the exact problem text as one message. Do not summarize it.",
            "Sorunun tam metnini tek mesaj olarak yapıştır. Özetleme.",
        ),
        "subject": (
            "Which subject is this question from? If you do not know, type “skip”.",
            "Bu soru hangi dersten? Bilmiyorsan “atla” yaz.",
        ),
        "topic": (
            "Which topic is this question about? If you do not know, type “skip”.",
            "Bu soru hangi konuyla ilgili? Bilmiyorsan “atla” yaz.",
        ),
    }
    return [questions[field][0 if language == "en" else 1]]


def _preview_digest(messages: list[str], language: str, fields: dict, evidence: dict) -> str:
    encoded = json.dumps({"messages": messages, "language": language, "fields": fields, "evidence": evidence},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_question_capture(messages: list[str], language: str, evidence_claims: list[Mapping[str, Any]] | list[QuestionQuote]) -> dict[str, Any]:
    """Validate sequential, whole-turn quotes and build a preview without writing."""
    _validate_messages(messages, language)
    claims = [item if isinstance(item, QuestionQuote) else QuestionQuote.model_validate(item) for item in evidence_claims]
    accepted: dict[str, str] = {}
    verified: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, str]] = []
    expected_index = 0
    last_turn = -1
    ambiguous: dict[str, list[str]] = {}
    for claim in claims:
        field = QUESTION_FIELDS[expected_index] if expected_index < len(QUESTION_FIELDS) else None
        occurrences = [(index, start, end) for index, message in enumerate(messages)
                       for start, end in _occurrences(message, claim.quote)]
        repeated_optional_skip = (
            claim.field in {"subject", "topic"} and _is_skip(claim.quote, language)
        )
        if field is not None and claim.field == field and len(occurrences) > 1 and not repeated_optional_skip:
            ambiguous[field] = [claim.quote]
            rejected.append({"field": field, "reason": "quote_not_unique_in_student_messages"})
            break
        if (field is None or claim.field != field
                or (len(occurrences) != 1 and not repeated_optional_skip)):
            rejected.append({"field": claim.field, "reason": "field_order_or_quote_ambiguous"})
            continue
        if repeated_optional_skip:
            occurrences = [item for item in occurrences if item[0] > last_turn]
            if not occurrences:
                ambiguous[field] = [claim.quote]
                rejected.append({"field": field, "reason": "quote_not_in_next_student_turn"})
                break
        turn, start, end = occurrences[0]
        if turn <= last_turn or claim.quote != messages[turn]:
            ambiguous[field] = [claim.quote]
            rejected.append({"field": field, "reason": "quote_must_be_the_exact_current_turn"})
            break
        value = claim.quote
        skipped = field in {"subject", "topic"} and _is_skip(value, language)
        if field == "question_text":
            try:
                require_utf8_byte_limit(value, MAX_QUESTION_TEXT_BYTES, "question_text")
            except ValueError:
                ambiguous[field] = [claim.quote]
                rejected.append({"field": field, "reason": "question_text_outside_field_bounds"})
                break
            if len(value.strip()) < 3 or _META_INTENT.match(value.strip()):
                ambiguous[field] = [claim.quote]
                rejected.append({"field": field, "reason": "not_explicit_question_text"})
                break
        elif not skipped:
            limit = QUESTION_FIELD_LIMITS[field]
            if len(value.strip()) > limit or _UNCERTAIN_LABEL.match(value.strip()) or _META_INTENT.match(value.strip()):
                ambiguous[field] = [claim.quote]
                rejected.append({"field": field, "reason": "label_is_ambiguous_or_outside_field_bounds"})
                break
        accepted[field] = "" if skipped else value
        verified[field] = {"value": "" if skipped else value, "message_index": turn,
                           "quote": claim.quote, "start": start, "end": end, "skipped": skipped}
        expected_index += 1
        last_turn = turn

    missing = [field for field in QUESTION_FIELDS if field not in accepted and field not in ambiguous]
    expected = QUESTION_FIELDS[expected_index] if expected_index < len(QUESTION_FIELDS) else None
    ready = not missing and not ambiguous and len(accepted) == len(QUESTION_FIELDS)
    fields = ({"question_text": accepted["question_text"], "subject": accepted["subject"], "topic": accepted["topic"]}
              if ready else dict(accepted))
    status = "ready" if ready else "ambiguous" if expected in ambiguous or ambiguous else "incomplete"
    digest = _preview_digest(messages, language, fields, verified) if ready else None
    return {
        "status": status, "language": language, "fields": fields, "verified_evidence": verified,
        "evidence_claims": [{"field": item.field, "quote": item.quote} for item in claims],
        "verified_claims": [{"field": field, "quote": item["quote"]} for field, item in verified.items()],
        "missing": missing, "ambiguous": ambiguous, "expected_field": expected,
        "questions": _questions(language, expected) if expected else [], "preview_digest": digest,
        "rejected_claims": rejected, "write_allowed": False,
    }


def dispatch_provider_tool(arguments: Mapping[str, Any], *, messages: list[str], language: str) -> dict[str, Any]:
    parsed = QuestionToolArguments.model_validate(arguments)
    return prepare_question_capture(messages, language, parsed.evidence)
