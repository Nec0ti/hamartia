"""Host-verified, read-only evidence preparation for learning-evidence records."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.models.schemas import LearningEvidenceCreate

PROVIDER_TOOL_NAME = "hamartia_learning_evidence_prepare"
REQUIRED_FIELDS = ("activity", "subject", "topic", "date", "observation")
OPTIONAL_FIELDS = ("reference_url",)
FIELDS = (*REQUIRED_FIELDS, *OPTIONAL_FIELDS)
FIELD_LIMITS = {"date": 10, "subject": 120, "topic": 160, "activity": 500, "observation": 3000, "reference_url": 2048}
MAX_MESSAGES = 30
MAX_MESSAGE_LENGTH = 4000


class LearningEvidenceQuote(BaseModel):
    """An untrusted provider hint that must match one current user turn exactly."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: Literal["date", "subject", "topic", "activity", "observation", "reference_url"]
    quote: str = Field(min_length=1, max_length=3000)


class ProviderToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence: list[LearningEvidenceQuote] = Field(max_length=12)


def provider_tool_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "evidence": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "enum": list(FIELDS)},
                    "quote": {"type": "string", "minLength": 1, "maxLength": 3000},
                    },
                    "required": ["field", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["evidence"],
        "additionalProperties": False,
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


_EN_COMPLETION = re.compile(
    r"(?i)\bI\s+(?:(?:have|had)\s+)?(?:completed|finished|solved|read|reviewed|studied|practiced|"
    r"practised|wrote|worked|built|tested|summarized|summarised|explained|answered|attempted|"
    r"watched|listened|applied|prepared|revised)\b"
)
_TR_COMPLETION = re.compile(
    r"(?i)(?:\b(?:çözdüm|okudum|çalıştım|bitirdim|tamamladım|tekrar\s+ettim|yazdım|özetledim|"
    r"denedim|cevapladım|hazırladım|izledim|dinledim|uyguladım|inceledim)\b)"
)
_UNCERTAIN_OR_NEGATED = re.compile(
    r"(?i)(?:\b(?:not|never|didn't|didn.t|don't|don.t|haven't|haven.t|hasn't|hasn.t|hadn't|hadn.t|"
    r"won't|won.t|might|maybe|perhaps|possibly|probably|would|could|plan(?:ned)?\s+to|intend\s+to|"
    r"not\s+yet|haven't\s+finished|haven.t\s+finished)\b|"
    r"\b(?:değil|degil|yapmadım|yapmadim|çözmedim|cozmedim|okumadım|okumadim|çalışmadım|calismadim|"
    r"bitirmedim|tamamlamadım|tamamlamadim|henüz|henüz|belki|olabilir|düşünüyorum|dusunuyorum|"
    r"planlıyorum|planliyorum|yapacağım|yapacagim|çözeceğim|cozecegim)\b|[?？])"
)


def _activity_is_explicit_completion(value: str) -> bool:
    if _UNCERTAIN_OR_NEGATED.search(value):
        return False
    return bool(_EN_COMPLETION.search(value) or _TR_COMPLETION.search(value))


def _date_from_quote(quote: str) -> str | None:
    matches = re.findall(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", quote)
    if len(matches) != 1:
        return None
    candidate = matches[0]
    try:
        parsed = LearningEvidenceCreate.model_validate({
            "date": candidate, "subject": "x", "topic": "x", "activity": "x", "observation": "x",
        })
    except ValidationError:
        return None
    return parsed.date


def _url_from_quote(quote: str) -> str | None:
    matches = re.findall(r"https?://[^\s<>\"'`]+", quote, flags=re.IGNORECASE)
    if len(matches) != 1:
        return None
    candidate = matches[0].rstrip(".,;!?)\u3002")
    if quote.count(candidate) != 1:
        return None
    try:
        LearningEvidenceCreate.model_validate({
            "date": "2026-01-01", "subject": "x", "topic": "x", "activity": "x",
            "observation": "x", "reference_url": candidate,
        })
    except ValidationError:
        return None
    return candidate


def _questions(language: str, field: str) -> list[str]:
    labels = {
        "activity": ("What activity have you already completed? State it as your own completed action.", "Hangi etkinliği zaten tamamladın? Kendi tamamlanmış eylemin olarak belirt."),
        "subject": ("Which subject was the activity for?", "Etkinlik hangi ders içindi?"),
        "topic": ("Which topic did you work on?", "Hangi konuda çalıştın?"),
        "date": ("What date did you complete it? Reply with an explicit YYYY-MM-DD date.", "Etkinliği hangi tarihte tamamladın? Açıkça YYYY-MM-DD biçiminde yanıtla."),
        "observation": ("What did you observe or produce? Describe it in your own words.", "Ne gözlemledin veya ne ortaya çıkardın? Kendi sözlerinle anlat."),
        "reference_url": ("If you want to attach a reference, provide its exact URL; otherwise leave it out.", "Kaynak eklemek istersen tam adresini yaz; istemiyorsan boş bırak."),
    }
    return [labels[field][0 if language == "en" else 1]]


def _digest(messages: list[str], language: str, fields: dict, evidence: dict) -> str:
    encoded = json.dumps({
        "messages": messages,
        "language": language,
        "fields": fields,
        "evidence": evidence,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_learning_evidence(
    messages: list[str], language: str, evidence_claims: list[Mapping[str, Any]] | list[LearningEvidenceQuote],
) -> dict[str, Any]:
    """Verify one expected field per user turn and build a read-only exact preview."""
    _validate_messages(messages, language)
    parsed_claims = [item if isinstance(item, LearningEvidenceQuote) else LearningEvidenceQuote.model_validate(item)
                     for item in evidence_claims]
    claims_by_turn: dict[int, list[LearningEvidenceQuote]] = {}
    rejected: list[dict[str, str]] = []
    for claim in parsed_claims:
        occurrences = [
            (index, start, end)
            for index, message in enumerate(messages)
            for start, end in _occurrences(message, claim.quote)
        ]
        if len(occurrences) != 1:
            rejected.append({"field": claim.field, "reason": "quote_not_unique_in_student_messages"})
            continue
        turn, _, _ = occurrences[0]
        claims_by_turn.setdefault(turn, []).append(claim)

    accepted: dict[str, str] = {}
    verified: dict[str, dict[str, Any]] = {}
    ambiguous: dict[str, list[str]] = {}
    expected_index = 0
    for turn, message in enumerate(messages):
        if expected_index >= len(REQUIRED_FIELDS):
            break
        expected_field = REQUIRED_FIELDS[expected_index]
        turn_claims = claims_by_turn.get(turn, [])
        matching = [claim for claim in turn_claims if claim.field == expected_field]
        wrong = [claim for claim in turn_claims if claim.field != expected_field]
        for claim in wrong:
            rejected.append({"field": claim.field, "reason": "field_not_expected_for_this_turn"})
        if len(matching) != 1:
            if matching:
                ambiguous[expected_field] = [claim.quote for claim in matching]
                rejected.extend({"field": expected_field, "reason": "multiple_claims_for_expected_turn"} for _ in matching)
            continue
        claim = matching[0]
        occurrence = _occurrences(message, claim.quote)
        if len(occurrence) != 1:
            ambiguous[expected_field] = [claim.quote]
            rejected.append({"field": expected_field, "reason": "quote_not_unique_in_current_turn"})
            continue
        start, end = occurrence[0]
        quote = claim.quote
        if expected_field == "activity":
            value = quote.strip()
            if not _activity_is_explicit_completion(value):
                ambiguous[expected_field] = [quote]
                rejected.append({"field": expected_field, "reason": "completion_not_explicit_or_is_uncertain"})
                continue
        elif expected_field == "date":
            value = _date_from_quote(quote)
            if value is None:
                ambiguous[expected_field] = [quote]
                rejected.append({"field": expected_field, "reason": "date_not_explicit_valid_iso"})
                continue
        else:
            value = quote.strip()
        if not value or len(value) > FIELD_LIMITS[expected_field]:
            ambiguous[expected_field] = [quote]
            rejected.append({"field": expected_field, "reason": "value_outside_field_bounds"})
            continue
        accepted[expected_field] = value
        verified[expected_field] = {
            "value": value,
            "message_index": turn,
            "quote": quote,
            "start": start,
            "end": end,
        }
        expected_index += 1

    # Optional URLs are accepted only from exact, unique user text and validated without fetching.
    for claim in parsed_claims:
        if claim.field != "reference_url" or "reference_url" in accepted:
            continue
        occurrences = [
            (index, start, end)
            for index, message in enumerate(messages)
            for start, end in _occurrences(message, claim.quote)
        ]
        if len(occurrences) != 1:
            rejected.append({"field": "reference_url", "reason": "url_quote_not_unique_in_student_messages"})
            continue
        turn, start, end = occurrences[0]
        value = _url_from_quote(claim.quote)
        if value is None:
            ambiguous["reference_url"] = [claim.quote]
            rejected.append({"field": "reference_url", "reason": "url_not_explicit_valid_http_url"})
            continue
        accepted["reference_url"] = value
        verified["reference_url"] = {
            "value": value,
            "message_index": turn,
            "quote": claim.quote,
            "start": start,
            "end": end,
        }

    missing = [field for field in REQUIRED_FIELDS if field not in accepted and field not in ambiguous]
    # Only the next expected required field is actionable; do not accept later-field hints out of sequence.
    if missing:
        expected = REQUIRED_FIELDS[expected_index] if expected_index < len(REQUIRED_FIELDS) else missing[0]
        questions = _questions(language, expected)
        status = "ambiguous" if expected in ambiguous else "incomplete"
        fields = dict(accepted)
        digest = None
    else:
        fields = {**{field: accepted[field] for field in REQUIRED_FIELDS}, "reference_url": accepted.get("reference_url", "")}
        try:
            payload = LearningEvidenceCreate.model_validate(fields)
        except ValidationError:
            # Do not echo source text in an error. Ask for the next field in this one-turn protocol.
            field = next((field for field in REQUIRED_FIELDS if field in fields and len(str(fields[field])) > FIELD_LIMITS.get(field, 99999)), "observation")
            ambiguous[field] = [verified.get(field, {}).get("quote", "")]
            status = "ambiguous"
            missing = []
            questions = _questions(language, field)
            fields = {key: value for key, value in fields.items() if key != field}
            digest = None
        else:
            fields = payload.model_dump()
            questions = []
            status = "ready"
            digest = _digest(messages, language, fields, verified)

    return {
        "status": status,
        "fields": fields,
        "verified_evidence": verified,
        "evidence_claims": [{"field": item.field, "quote": item.quote} for item in parsed_claims],
        "missing": missing,
        "ambiguous": ambiguous,
        "questions": questions,
        "preview_digest": digest,
        "rejected_claims": rejected,
        "write_allowed": False,
    }


def dispatch_provider_tool(
    arguments: Mapping[str, Any], *, messages: list[str], language: str,
) -> dict[str, Any]:
    tool_args = ProviderToolArguments.model_validate(arguments)
    return prepare_learning_evidence(messages, language, tool_args.evidence)
