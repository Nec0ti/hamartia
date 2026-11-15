"""Deterministic evidence extraction for the create-only Study Agent practice flow."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.models.schemas import PracticeSessionCreate

FIELDS = (
    "date", "subject", "topic", "correct", "incorrect", "blank",
    "duration_minutes", "duration_seconds",
)
ALIASES = {
    "date": "date|tarih",
    "subject": "subject|ders",
    "topic": "topic|konu",
    "correct": "correct|doğru|dogru",
    "incorrect": "incorrect|wrong|yanlış|yanlis",
    "blank": "blank|boş|bos",
    "duration_minutes": "duration_minutes|minutes|dakika|süre_dakika|sure_dakika",
    "duration_seconds": "duration_seconds|seconds|saniye|süre_saniye|sure_saniye",
}


@dataclass(frozen=True)
class Evidence:
    value: str | int
    message_index: int
    quote: str


def _patterns(field: str) -> list[re.Pattern]:
    labels = rf"(?<!\w)(?:{ALIASES[field]})(?!\w)"
    if field in {"subject", "topic"}:
        return [re.compile(rf"(?im)^\s*(?:{labels})\s*:\s*([^\n,;]{{1,160}})\s*$")]
    if field == "date":
        return [re.compile(rf"(?i)(?:{labels})\s*:\s*(\d{{4}}-\d{{2}}-\d{{2}})")]
    if field in {"correct", "incorrect", "blank"}:
        return [re.compile(rf"(?i)(?:{labels})\s*:\s*(\d{{1,5}})\b")]
    unit_labels = ALIASES[field]
    return [re.compile(rf"(?i)(?:{unit_labels})\s*:\s*(\d{{1,5}})\b")]


def extract_fields(messages: list[str]) -> tuple[dict[str, Evidence], dict[str, list[str]]]:
    """Extract only explicitly labeled values; conflicting values in one turn stay unresolved."""
    accepted: dict[str, Evidence] = {}
    ambiguous: dict[str, list[str]] = {}
    for index, message in enumerate(messages):
        for field in FIELDS:
            found: list[tuple[str | int, str]] = []
            for pattern in _patterns(field):
                for match in pattern.finditer(message):
                    raw = match.group(1).strip()
                    value = int(raw) if field in {"correct", "incorrect", "blank", "duration_minutes", "duration_seconds"} else raw
                    found.append((value, match.group(0).strip()))
            if not found:
                continue
            distinct = {value for value, _ in found}
            if len(distinct) != 1:
                ambiguous[field] = [quote for _, quote in found]
                accepted.pop(field, None)
                continue
            value, quote = found[-1]
            accepted[field] = Evidence(value, index, quote)
            ambiguous.pop(field, None)
    return accepted, ambiguous


def complete_payload(messages: list[str]) -> tuple[PracticeSessionCreate | None, dict, dict]:
    evidence, ambiguous = extract_fields(messages)
    missing = [field for field in FIELDS if field not in evidence and field not in ambiguous]
    if missing or ambiguous:
        return None, {field: evidence[field].value for field in evidence}, {
            "missing": missing,
            "ambiguous": ambiguous,
            "evidence": {field: evidence[field].__dict__ for field in evidence},
        }
    raw = {field: evidence[field].value for field in FIELDS}
    payload = PracticeSessionCreate.model_validate(raw)
    return payload, raw, {"missing": [], "ambiguous": {}, "evidence": {field: evidence[field].__dict__ for field in evidence}}


def preview_digest(payload: PracticeSessionCreate, evidence: dict) -> str:
    canonical = {"fields": payload.model_dump(), "evidence": evidence}
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parse_proposal(raw: str) -> dict[str, str | int]:
    """Parse a closed JSON envelope; model output never becomes a write payload."""
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("The provider response was not valid JSON.") from exc
    if not isinstance(value, dict) or set(value) != {"fields"} or not isinstance(value["fields"], dict):
        raise ValueError("The provider response must contain only a fields object.")
    fields = value["fields"]
    if set(fields) - set(FIELDS) or any(
        type(item) is not (str if field in {"date", "subject", "topic"} else int)
        for field, item in fields.items()
    ):
        raise ValueError("The provider response contains unsupported study fields or values.")
    return fields


def questions(language: str, missing: list[str], ambiguous: dict[str, list[str]]) -> list[str]:
    labels = {
        "en": {
            "date": "date (YYYY-MM-DD)", "subject": "subject", "topic": "topic",
            "correct": "correct count", "incorrect": "incorrect count", "blank": "blank count",
            "duration_minutes": "duration in minutes", "duration_seconds": "additional duration seconds",
        },
        "tr": {
            "date": "tarih (YYYY-MM-DD)", "subject": "ders", "topic": "konu",
            "correct": "doğru sayısı", "incorrect": "yanlış sayısı", "blank": "boş sayısı",
            "duration_minutes": "süre (dakika)", "duration_seconds": "ek süre (saniye)",
        },
    }[language]
    keys = {
        "date": "date", "subject": "subject", "topic": "topic", "correct": "correct",
        "incorrect": "incorrect", "blank": "blank", "duration_minutes": "duration_minutes",
        "duration_seconds": "duration_seconds",
    }
    if language == "en":
        result = [f"Please provide {labels[field]} as `{keys[field]}: value`." for field in missing]
        result.extend(f"I found conflicting values for {labels[field]}: {', '.join(values)}. Please send one corrected `{keys[field]}: value`." for field, values in ambiguous.items())
    else:
        result = [f"Lütfen {labels[field]} bilgisini `{keys[field]}: değer` biçiminde belirt." for field in missing]
        result.extend(f"{labels[field]} için çelişen değerler buldum: {', '.join(values)}. Lütfen düzeltilmiş tek bir `{keys[field]}: değer` gönder." for field, values in ambiguous.items())
    return result
