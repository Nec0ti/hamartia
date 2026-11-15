"""Allowlisted, read-only tool contract for conversational practice entry."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.models.schemas import PracticeSessionCreate
from app.services.study_agent_practice import (
    FIELDS,
    Evidence,
    complete_payload,
    extract_fields,
    preview_digest,
)


class EvidenceQuote(BaseModel):
    """A provider-suggested quote; both field and quote must be verified locally."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: str
    quote: str = Field(min_length=1, max_length=500)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if value not in FIELDS:
            raise ValueError("Unsupported practice field.")
        return value


class PrepareCommand(BaseModel):
    """Strict JSON-lines CLI request. This command can never write data."""

    model_config = ConfigDict(extra="forbid", strict=True)

    command: str
    language: str
    messages: list[str] = Field(min_length=1, max_length=30)
    evidence: list[EvidenceQuote] = Field(default_factory=list, max_length=40)


class ProviderToolArguments(BaseModel):
    """Model-callable schema: no transcript, language, index, value, or path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    evidence: list[EvidenceQuote] = Field(max_length=40)


def _field(value: str) -> str:
    if value not in FIELDS:
        raise ValueError("Unsupported practice field.")
    return value


def _occurrences(messages: list[str], quote: str) -> list[tuple[int, int, int]]:
    found = []
    for message_index, message in enumerate(messages):
        offset = message.find(quote)
        while offset >= 0:
            found.append((message_index, offset, offset + len(quote)))
            offset = message.find(quote, offset + 1)
    return found


def _sentence_context(message: str, start: int, end: int) -> str:
    boundaries = (".", "?", "!", ";", "\n")
    left_boundary = max((message.rfind(mark, 0, start) for mark in boundaries), default=-1)
    right_candidates = [message.find(mark, end) for mark in boundaries]
    right_boundary = min((position for position in right_candidates if position >= 0), default=len(message))
    left = left_boundary + 1
    right = right_boundary

    # Explicit correction markers can occur inline after a comma or dash, not
    # only at the beginning of a new sentence or transcript turn.
    sentence = message[left:right]
    for correction in _CORRECTION_MARKER.finditer(sentence):
        marker_start = left + correction.start("marker")
        if marker_start < start:
            left = marker_start
        elif marker_start >= end:
            right = marker_start
            break
    context = message[left:right].strip()
    continuation = r"(?i)^\s*,?\s*(?:or|either|veya|ya\s+da|plus|and|ve|ile|ek|ilave|maybe|perhaps|alternatively|belki|galiba)\b"
    correction_start = rf"(?i)^\s*(?:and\s+)?{_CORRECTION_CUE}"

    # Keep a neighboring clause with the quoted statement only when it begins
    # with a connector. This catches punctuation-split alternatives without
    # merging ordinary separate statements or explicit corrections.
    if left_boundary >= 0 and re.match(continuation, context) and not re.match(correction_start, context):
        previous_left_candidates = [message.rfind(mark, 0, left_boundary) for mark in boundaries]
        previous_left = max(previous_left_candidates, default=-1) + 1
        context = f"{message[previous_left:left_boundary].strip()} {context}".strip()
    if right_boundary < len(message):
        next_left = right_boundary + 1
        next_right_candidates = [message.find(mark, next_left) for mark in boundaries]
        next_right = min((position for position in next_right_candidates if position >= 0), default=len(message))
        following = message[next_left:next_right].strip()
        if re.match(continuation, following) and not re.match(correction_start, following):
            context = f"{context} {following}".strip()
    return context


def _number_has_unsafe_boundary(candidate: str, context: str, match: re.Match[str]) -> bool:
    context_offset = context.find(candidate)
    if context_offset < 0:
        context_offset = 0
    start = context_offset + match.start(1)
    end = context_offset + match.end(1)
    if start > 0 and context[start - 1] in "-+.,":
        return True
    if re.search(r"\d\s+$", context[:start]):
        return True
    if end < len(context) and context[end] in ".,":
        if end + 1 < len(context) and context[end + 1].isdigit():
            return True
        if context[end] == ".":
            return True
    return False


_HEDGE_OR_NEGATION = re.compile(
    r"(?i)(?:\bnot\b|\bno\b|\bnever\b|\bdidn't\b|\bdidnt\b|\bwasn't\b|\bwasnt\b|\bhaven't\b|\bhavent\b|\bmaybe\b|\bperhaps\b|\babout\s+\d|\baround\s+\d|\bat\s+least\s+\d|\bapproximately\b|\bapprox\.?\b|\broughly\b|\bprobably\b|\bi think\b|\bi guess\b|\bif\b|\bwhether\b|\bcould\b|\bwould\b|\bsuppose\b|\bimagine\b|\bhypothetical\b|\bexample\b|\bteacher\s+(?:said|says)\b|\b(?:he|she|they)\s+said\b|\bnet\b|\byaklaşık\b|\bcivarında\b|\bbelki\b|\bsanırım\b|\bgaliba\b|\bdeğil\b|\byok\b|\byapmadım\b|\bhiçbir\b|\bvarsay\w*\b|\bolsaydı\b|\börneğin\b|\böğretmen\w*\s+(?:dedi|söyledi)\b|\b(?:dedi|söyledi)\b)"
)
_ALTERNATIVE_MARKER = re.compile(r"(?i)\b(?:alternatively|as an alternative|other option|belki|galiba)\b")
_UNPUNCTUATED_QUESTION = re.compile(
    r"(?i)(?:^\s*(?:did|do|does|is|are|was|were|can|could|would|should|what|when|where|why|how|whether|kaç|ne|hangi|mi|mı|mu|mü)\b|\b(?:mi|mı|mu|mü)\s*$)"
)
_DATE_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)"
_DATE_CANDIDATE_PATTERN = rf"(?<!\w)(?:\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|{_DATE_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|\d{{1,2}}\s+{_DATE_MONTH}\.?(?:\s+\d{{4}})?)(?!\w)"
_DATE_CANDIDATES = re.compile(
    rf"(?i){_DATE_CANDIDATE_PATTERN}"
)
_DATE_SHORTHAND_ALTERNATIVE = re.compile(rf"(?i){_DATE_CANDIDATE_PATTERN}\s*[,;.!?]*\s*(?:or|either|veya|ya\s+da)\s+(?:\d{{1,2}}(?:st|nd|rd|th)?(?:[/.-]\d{{1,2}})?)(?![\d:])")
_NUMBER_WORD = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|a|an|sıfır|bir|iki|üç|uc|dört|dort|beş|bes|altı|alti|yedi|sekiz|dokuz|on|on\s+bir|on\s+iki|yirmi|otuz|kırk|kirk|elli|altmış|altmis|yetmiş|yetmis|seksen|doksan)"
_COUNT_NUMBER = rf"(?:\d{{1,5}}|{_NUMBER_WORD})"
_RELATIVE_DATE_UNIT = r"(?:days?|weeks?|months?|years?|hours?|gün|hafta|ay|yıl|yil|sene|saat)"
_RELATIVE_DATE_OFFSET = rf"(?:(?:(?:in|within)\s+)?{_COUNT_NUMBER}\s+{_RELATIVE_DATE_UNIT}(?:\s+(?:later|afterwards?|after(?:\s+that)?|from\s+now|sonra))?)"
_RELATIVE_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|pazartesi|salı|sali|çarşamba|carsamba|perşembe|persembe|cuma|cumartesi|pazar)"
_RELATIVE_DATE_QUALIFIER = rf"(?:(?:(?:in|within)\s+)?(?:the\s+)?(?:next|following|upcoming|gelecek|önümüzdeki)\s+(?:day|week|month|year|hour|gün|hafta|ay|yıl|yil|sene|saat|{_RELATIVE_WEEKDAY})|(?:(?:the\s+)?(?:last|past|previous|next|coming|upcoming|geçen|gecen|gelecek|önümüzdeki|önceki))\s+{_RELATIVE_WEEKDAY}|bir\s+sonraki\s+(?:day|week|month|year|hour|gün|hafta|ay|yıl|yil|sene|saat|{_RELATIVE_WEEKDAY}))"
_RELATIVE_DATE_PAST_OFFSET = rf"(?:{_COUNT_NUMBER}\s+{_RELATIVE_DATE_UNIT}\s+(?:ago|before|earlier|önce|once))"
_RELATIVE_DATE_PAST_QUALIFIER = r"(?:yesterday|(?:(?:the\s+)?(?:last|past|previous)|geçen|gecen|önceki)\s+(?:day|week|month|year|hour|gün|hafta|ay|yıl|yil|sene|saat)|(?:the\s+)?day\s+before(?:\s+that)?|dün|dun|(?:bir\s+)?gün\s+önce)"
_RELATIVE_DATE_COMPACT_OFFSET = r"\d{1,5}(?:yrs?|y|d|w|h)(?:\s+(?:later|afterwards?|after(?:\s+that)?|ago|before|earlier|sonra|önce|once))?"
_DATE_RELATIVE_ALTERNATIVE = re.compile(
    rf"(?i){_DATE_CANDIDATE_PATTERN}\s*[,;.!?—–-]*\s*(?:or|either|veya|ya\s+da)\s+"
    rf"(?:tomorrow|{_RELATIVE_DATE_PAST_QUALIFIER}|{_RELATIVE_DATE_PAST_OFFSET}|{_RELATIVE_DATE_QUALIFIER}|{_RELATIVE_DATE_COMPACT_OFFSET}|(?:the\s+)?(?:next|following)\s+day|(?:the\s+)?day\s+(?:after(?:\s+that)?|afterwards?)|"
    rf"(?:a|one)\s+day\s+(?:later|after(?:\s+that)?|afterwards?)|yarın|yarin|(?:bir\s+)?sonraki\s+gün|ertesi\s+gün|"
    rf"{_RELATIVE_DATE_OFFSET})\b"
)
_COUNT_CONNECTOR = r"(?:,\s*(?:(?:or|and|to|veya|ya\s+da|ile|ila)\s*)?|\s+(?:or|and|to|veya|ya\s+da|ile|ila|[-–])\s+)"
_DURATION_VALUE = rf"(?:{_COUNT_NUMBER}|\d+\s*/\s*\d+|[½¼¾⅓⅔⅛⅜⅝⅞]|half(?:\s+an)?|a\s+half|one\s+and\s+a\s+half|bir\s+buçuk|yarım)"
_DURATION_CHUNK = rf"{_DURATION_VALUE}\s*(?:hours?|hrs?|h|saat|minutes?|mins?|dakika|seconds?|secs?|saniye)\b"
_HOUR_DURATION = re.compile(rf"(?i){_DURATION_VALUE}\s*(?:hours?|hrs?|h|saat)\b")
_DURATION_ALTERNATIVE = re.compile(rf"(?i){_DURATION_CHUNK}(?:\s+(?:or|either|veya|ya\s+da)\s+|\s+(?:or|veya)\s+){_DURATION_CHUNK}")
_DURATION_ADDITIVE_CONNECTOR = r"(?:and|plus|ve|ile|ek|ilave)"
_DURATION_MINUTES_ADDITIVE = re.compile(rf"(?i){_DURATION_VALUE}\s*(?:minutes?|mins?|dakika)\s*[,;]?\s+{_DURATION_ADDITIVE_CONNECTOR}\s+{_DURATION_VALUE}\s*(?:minutes?|mins?|dakika)\b")
_DURATION_SECONDS_ADDITIVE = re.compile(rf"(?i){_DURATION_VALUE}\s*(?:seconds?|secs?|saniye)\s*[,;]?\s+{_DURATION_ADDITIVE_CONNECTOR}\s+{_DURATION_VALUE}\s*(?:seconds?|secs?|saniye)\b")
_DURATION_FRACTIONAL = re.compile(r"(?i)(?<!\w)(?:\d{1,5}[.,]\d+|\d+\s*/\s*\d+|[½¼¾⅓⅔⅛⅜⅝⅞])\s*(?:hours?|hrs?|h|saat|minutes?|mins?|dakika|seconds?|secs?|saniye)\b")
_COUNT_ALTERNATIVES: dict[str, re.Pattern[str]] = {
    "correct": re.compile(rf"(?i)(?:\bbetween\s+{_COUNT_NUMBER}\s+(?:and|to)\s+{_COUNT_NUMBER}|\b{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER})\s*(?:questions?\s+|answers?\s+)?(?:correct(?:ly)?|right|doğru|dogru)\b|\b(?:correct|doğru|dogru)\s*:\s*{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER}"),
    "incorrect": re.compile(rf"(?i)(?:\bbetween\s+{_COUNT_NUMBER}\s+(?:and|to)\s+{_COUNT_NUMBER}|\b{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER})\s*(?:questions?\s+|answers?\s+)?(?:incorrect(?:ly)?|wrong|yanlış|yanlis)\b|\b(?:incorrect|wrong|yanlış|yanlis)\s*:\s*{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER}"),
    "blank": re.compile(rf"(?i)(?:\bbetween\s+{_COUNT_NUMBER}\s+(?:and|to)\s+{_COUNT_NUMBER}|\b{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER})\s*(?:questions?\s+)?(?:blank|boş|bos)\b|\b(?:blank|boş|bos)\s*:\s*{_COUNT_NUMBER}{_COUNT_CONNECTOR}{_COUNT_NUMBER}"),
}

_COUNT_PATTERNS: dict[str, re.Pattern[str]] = {
    "correct": re.compile(r"(?i)(?<![\w.,+\-])(?:(?:i\s+)?(?:got|answered|solved|have)\s+)?(\d{1,5})(?![\d.,])\s*(?:questions?\s+)?(?:correct(?:ly)?|right|doğru|dogru)(?![\w])"),
    "incorrect": re.compile(r"(?i)(?<![\w.,+\-])(?:(?:i\s+)?(?:got|answered|solved|have)\s+)?(\d{1,5})(?![\d.,])\s*(?:questions?\s+)?(?:incorrect(?:ly)?|wrong|yanlış|yanlis)(?![\w])"),
    "blank": re.compile(r"(?i)(?<![\w.,+\-])(?:(?:i\s+)?(?:left|had|have)\s+)?(\d{1,5})(?![\d.,])\s*(?:questions?\s+)?(?:blank|boş|bos)(?![\w])"),
}
_DURATION_MINUTES = re.compile(r"(?i)(?<![\w.,+\-])(?:(?:it\s+)?(?:took|spent)\s+)?(\d{1,4})(?![\d.,])\s*(?:minutes?|mins?|dakika)(?![\w])")
_DURATION_SECONDS = re.compile(r"(?i)(?<![\w.,+\-])(?:(?:and|plus|ek|ilave)\s+)?(\d{1,4})(?![\d.,])\s*(?:seconds?|secs?|saniye)(?![\w])")
_DATE = re.compile(r"(?i)(?:\bdate(?:\s*:\s*|\s+)|\btarih(?:\s*:\s*|\s+)|\bon\s+|\bdated\s+|\btarihinde\s+)(\d{4}-\d{2}-\d{2})(?!\d)")
_SUBJECT_PATTERNS = (
    re.compile(r"(?i)(?:subject|class|course|ders)\s+(?:is|was|:|olarak|im|im:)?\s*([\wÇĞİÖŞÜçğıöşü& -]{2,60})"),
    re.compile(r"(?i)\b(?:in|for)\s+(?:my\s+)?([\wÇĞİÖŞÜçğıöşü& -]{2,50}?)\s+(?:class|course)\b"),
    re.compile(r"(?i)\bin\s+([\wÇĞİÖŞÜçğıöşü& -]{2,50}?)(?=\s+(?:on|about|today|yesterday|during|for)\b|[,;.!?]|$)"),
    re.compile(r"(?i)([\wÇĞİÖŞÜçğıöşü& -]{2,50}?)\s+dersinde\b"),
)
_TOPIC_PATTERNS = (
    re.compile(r"(?i)(?:topic|konu)\s+(?:is|was|:|olarak|şu|su)?\s*([\wÇĞİÖŞÜçğıöşü& -]{2,80})"),
    re.compile(r"(?i)\b(?:practiced|studied|reviewed|worked\s+on)\s+(?:the\s+)?([\wÇĞİÖŞÜçğıöşü& -]{2,70}?)(?=\s+(?:in|for|during)\b|[,.;!?]|$)"),
    re.compile(r"(?i)\bon\s+(?:the\s+)?([\wÇĞİÖŞÜçğıöşü& -]{2,70}?)(?=\s+in\s+|[,.;!?]|$)"),
    re.compile(r"(?i)dersinde\s+([\wÇĞİÖŞÜçğıöşü& -]{2,70}?)\s+(?:çalıştım|çalıştık|çözdüm|çözdük)\b"),
    re.compile(r"(?i)([\wÇĞİÖŞÜçğıöşü& -]{2,70}?)\s+(?:konusunu|konusunda|konusundan)\b"),
)
_CORRECTION_CUE = r"(?:(?:actually|aslında)\b|(?:correction|update|düzeltme|duzeltme|güncelleme|guncelleme)\s*:)"
_CORRECTION_MARKER = re.compile(
    rf"(?i)(?:^|[,;.!?—–-]\s*)(?P<marker>(?:and\s+)?{_CORRECTION_CUE})"
)


def parse_quote_value(field: str, quote: str, context: str | None = None) -> str | int | None:
    """Derive one value from a narrowly supported statement; never trust model values."""
    _field(field)
    candidate = quote.strip()
    surrounding = (context or candidate).strip()
    if (
        not candidate
        or "?" in surrounding
        or _UNPUNCTUATED_QUESTION.search(surrounding)
        or _HEDGE_OR_NEGATION.search(surrounding)
        or _ALTERNATIVE_MARKER.search(surrounding)
        or (field in {"duration_minutes", "duration_seconds"} and _HOUR_DURATION.search(surrounding))
        or (field in {"duration_minutes", "duration_seconds"} and _DURATION_ALTERNATIVE.search(surrounding))
        or (field == "duration_minutes" and _DURATION_MINUTES_ADDITIVE.search(surrounding))
        or (field == "duration_seconds" and _DURATION_SECONDS_ADDITIVE.search(surrounding))
        or (field in {"duration_minutes", "duration_seconds"} and _DURATION_FRACTIONAL.search(surrounding))
        or (field == "date" and (len(set(_DATE_CANDIDATES.findall(surrounding))) > 1 or _DATE_SHORTHAND_ALTERNATIVE.search(surrounding) or _DATE_RELATIVE_ALTERNATIVE.search(surrounding)))
        or (field in _COUNT_ALTERNATIVES and _COUNT_ALTERNATIVES[field].search(surrounding))
    ):
        return None
    parse_candidate = re.sub(
        r"(?i)^\s*(?:and\s+)?(?:correction|actually|update|düzeltme|duzeltme|aslında|güncelleme|guncelleme)\s*[:,]?\s*",
        "", candidate,
    )
    # Labeled text stays supported, but use the existing deterministic parser.
    parsed, ambiguous = extract_fields([parse_candidate])
    if field in ambiguous:
        return None
    if field in parsed:
        value = parsed[field].value
        if field in {"subject", "topic"} and re.search(r"(?i)\s+(?:and|or|&|ve|ile)\s+", str(value)):
            return None
        trusted, alternatives = _context_field_values(field, surrounding)
        if not trusted or (alternatives and alternatives != {value}):
            return None
        return value

    if field in _COUNT_PATTERNS:
        matches = list(_COUNT_PATTERNS[field].finditer(parse_candidate))
        if len(matches) == 1 and not _number_has_unsafe_boundary(parse_candidate, surrounding, matches[0]):
            value = int(matches[0].group(1))
            trusted, alternatives = _context_field_values(field, surrounding)
            return value if trusted and (not alternatives or alternatives == {value}) else None
        return None
    if field == "duration_minutes":
        matches = list(_DURATION_MINUTES.finditer(parse_candidate))
        if len(matches) == 1 and not _number_has_unsafe_boundary(parse_candidate, surrounding, matches[0]):
            value = int(matches[0].group(1))
            trusted, alternatives = _context_field_values(field, surrounding)
            return value if trusted and (not alternatives or alternatives == {value}) else None
        return None
    if field == "duration_seconds":
        matches = list(_DURATION_SECONDS.finditer(parse_candidate))
        if len(matches) == 1 and not _number_has_unsafe_boundary(parse_candidate, surrounding, matches[0]):
            value = int(matches[0].group(1))
            trusted, alternatives = _context_field_values(field, surrounding)
            return value if trusted and (not alternatives or alternatives == {value}) else None
        return None
    if field == "date":
        matches = list(_DATE.finditer(parse_candidate))
        if len(matches) == 1:
            value = matches[0].group(1)
            trusted, alternatives = _context_field_values(field, surrounding)
            return value if trusted and (not alternatives or alternatives == {value}) else None
        return None
    patterns = _SUBJECT_PATTERNS if field == "subject" else _TOPIC_PATTERNS
    matches = [match.group(1).strip(" .,:;!?\t\n") for pattern in patterns for match in pattern.finditer(parse_candidate)]
    matches = list(dict.fromkeys(
        value for value in matches
        if value and not re.fullmatch(r"(?:\d{4}-\d{2}-\d{2}|\d+)", value)
    ))
    if field == "topic" and any(re.search(r"(?i)\s+(?:and|&|ve|ile)\s+", value) for value in matches):
        return None
    if len(matches) != 1:
        return None
    value = matches[0]
    trusted, alternatives = _context_field_values(field, surrounding)
    return value if trusted and (not alternatives or alternatives == {value}) else None


def _context_field_values(field: str, context: str) -> tuple[bool, set[str | int]]:
    """Inspect the full sentence so a quote cannot select one of two facts."""
    explicit, explicit_ambiguous = extract_fields([context])
    if field in explicit_ambiguous:
        return False, set()
    values: set[str | int] = set()
    if field in explicit:
        values.add(explicit[field].value)
    if field in _COUNT_PATTERNS:
        pattern = _COUNT_PATTERNS[field]
    elif field == "duration_minutes":
        pattern = _DURATION_MINUTES
    elif field == "duration_seconds":
        pattern = _DURATION_SECONDS
    elif field == "date":
        pattern = _DATE
    else:
        patterns = _SUBJECT_PATTERNS if field == "subject" else _TOPIC_PATTERNS
        matches = [match.group(1).strip(" .,:;!?\t\n") for item in patterns for match in item.finditer(context)]
        matches = list(dict.fromkeys(
            value for value in matches
            if value and not re.fullmatch(r"(?:\d{4}-\d{2}-\d{2}|\d+)", value)
        ))
        if any(re.search(r"(?i)\s+(?:and|or|&|ve|ile)\s+", value) for value in matches):
            return False, set()
        values.update(matches)
        return True, values
    for match in pattern.finditer(context):
        if field in (set(_COUNT_PATTERNS) | {"duration_minutes", "duration_seconds"}) and _number_has_unsafe_boundary(context, context, match):
            continue
        values.add(int(match.group(1)) if field != "date" else match.group(1))
    return True, values


def _is_explicit_correction(context: str) -> bool:
    return bool(re.match(rf"(?i)^\s*(?:and\s+)?{_CORRECTION_CUE}", context))


def _transcript_field_resolution(field: str, messages: list[str]) -> tuple[bool, Evidence | None, list[str]]:
    """Resolve supported transcript candidates in host order, independent of provider quote hints."""
    events: list[tuple[int, int, Evidence | None, bool, str]] = []

    def add_candidate(index: int, quote: str, start: int, end: int, context: str) -> None:
        correction = _is_explicit_correction(context)
        occurrences = _occurrences(messages, quote)
        if correction:
            correction_quote = context.strip()
            correction_start = messages[index].find(correction_quote)
            if correction_start >= 0:
                quote = correction_quote
                start = correction_start
                end = start + len(quote)
                occurrences = _occurrences(messages, quote)
        if len(occurrences) != 1 or occurrences[0] != (index, start, end):
            events.append((index, start, None, False, quote))
            return
        value = parse_quote_value(field, quote, context)
        if value is None:
            events.append((index, start, None, False, quote))
            return
        events.append((index, start, Evidence(value, index, quote), correction, quote))

    for index, message in enumerate(messages):
        explicit, explicit_ambiguous = extract_fields([message])
        for quote in explicit_ambiguous.get(field, []):
            start = message.find(quote)
            context = _sentence_context(message, start, start + len(quote)) if start >= 0 else message
            events.append((index, max(start, 0), None, False, quote))
        if field in explicit and field not in explicit_ambiguous:
            quote = explicit[field].quote
            start = message.find(quote)
            context = _sentence_context(message, start, start + len(quote))
            add_candidate(index, quote, start, start + len(quote), context)

        if field in _COUNT_PATTERNS:
            patterns = (_COUNT_PATTERNS[field],)
        elif field == "duration_minutes":
            patterns = (_DURATION_MINUTES,)
        elif field == "duration_seconds":
            patterns = (_DURATION_SECONDS,)
        elif field == "date":
            patterns = (_DATE,)
        else:
            patterns = _SUBJECT_PATTERNS if field == "subject" else _TOPIC_PATTERNS
        seen: set[tuple[int, int]] = set()
        for pattern in patterns:
            for match in pattern.finditer(message):
                if field in {"subject", "topic"}:
                    candidate_value = match.group(1).strip()
                    if re.fullmatch(r"(?:\d{4}-\d{2}-\d{2}|\d+)", candidate_value) or _DATE_CANDIDATES.search(candidate_value):
                        continue
                start, end = match.span()
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                quote = match.group(0)
                context = _sentence_context(message, start, end)
                add_candidate(index, quote, start, end, context)

    if field == "date":
        joined = "\n".join(messages)
        message_starts: list[int] = []
        offset = 0
        for message in messages:
            message_starts.append(offset)
            offset += len(message) + 1
        for match in _DATE_RELATIVE_ALTERNATIVE.finditer(joined):
            index = max((i for i, start in enumerate(message_starts) if start <= match.start()), default=0)
            events.append((index, match.start() - message_starts[index], None, False, "relative date continuation"))

    events.sort(key=lambda item: (item[0], item[1]))
    current: Evidence | None = None
    current_is_correction = False
    unresolved = False
    ambiguous_quotes: list[str] = []
    for _index, _start, evidence, correction, quote in events:
        if evidence is None:
            unresolved = True
            current = None
            current_is_correction = False
            ambiguous_quotes.append(quote)
            continue
        if correction:
            current = evidence
            current_is_correction = True
            unresolved = False
            ambiguous_quotes = []
            continue
        if unresolved:
            ambiguous_quotes.append(quote)
            continue
        if current is None:
            current = evidence
            current_is_correction = False
        elif current.value != evidence.value:
            unresolved = True
            ambiguous_quotes.extend((current.quote, evidence.quote))
            current = None
            current_is_correction = False

    if unresolved:
        return True, None, list(dict.fromkeys(item for item in ambiguous_quotes if item))
    if current_is_correction:
        return False, current, []
    return False, None, []


def _conversation_questions(language: str, missing: list[str], ambiguous: dict[str, list[str]]) -> list[str]:
    prompts = {
        "en": {
            "date": "What date was this practice set? An unambiguous year-month-day date is best.",
            "subject": "Which subject was this practice set for?",
            "topic": "Which topic did you practice?",
            "correct": "How many answers were correct?",
            "incorrect": "How many were incorrect?",
            "blank": "How many questions did you leave blank?",
            "duration_minutes": "How many minutes did you spend on it?",
            "duration_seconds": "How many additional seconds did it take? If there were none, say zero.",
        },
        "tr": {
            "date": "Bu çalışma setini hangi tarihte yaptın? Yıl-ay-gün biçiminde açıkça söyleyebilirsin.",
            "subject": "Bu çalışma seti hangi ders içindi?",
            "topic": "Hangi konuda çalıştın?",
            "correct": "Kaç soruyu doğru yaptın?",
            "incorrect": "Kaç soruyu yanlış yaptın?",
            "blank": "Kaç soruyu boş bıraktın?",
            "duration_minutes": "Bu çalışma için kaç dakika harcadın?",
            "duration_seconds": "Ek olarak kaç saniye sürdü? Ek süre yoksa sıfır diyebilirsin.",
        },
    }[language]
    result = [prompts[field] for field in missing]
    for field, quotes in ambiguous.items():
        label = field.replace("_", " ") if language == "en" else {
            "correct": "doğru sayısı", "incorrect": "yanlış sayısı", "blank": "boş sayısı",
            "duration_minutes": "dakika", "duration_seconds": "saniye", "subject": "ders", "topic": "konu", "date": "tarih",
        }[field]
        if language == "en":
            result.append(f"I found conflicting or unclear statements for {label}: {'; '.join(quotes)}. Which value should I use? Please explicitly correct an earlier statement if needed.")
        else:
            result.append(f"{label.capitalize()} için çelişkili veya belirsiz ifadeler buldum: {'; '.join(quotes)}. Hangi değeri kullanmalıyım? Gerekirse önceki ifadeni açıkça düzelt.")
    return result


def prepare_practice(
    messages: list[str], language: str, evidence_claims: list[Mapping[str, Any]] | list[EvidenceQuote],
) -> dict[str, Any]:
    """Build a read-only, verified draft from source messages and provider quote hints."""
    if language not in {"en", "tr"}:
        raise ValueError("language must be en or tr")
    if not 1 <= len(messages) <= 30 or any(not isinstance(message, str) or not message.strip() or len(message) > 4000 for message in messages):
        raise ValueError("messages must contain 1 to 30 non-empty student messages of up to 4,000 characters")
    raw_accepted, ambiguous = extract_fields(messages)
    accepted: dict[str, Evidence] = {}
    rejected: list[dict[str, str]] = []
    # Even the built-in labeled parser is treated as a candidate: contextual
    # negation, hedging, hypotheticals, and reported speech remain unresolved.
    for field, raw_evidence in raw_accepted.items():
        occurrences = _occurrences(messages, raw_evidence.quote)
        if len(occurrences) != 1:
            ambiguous[field] = list(dict.fromkeys([*ambiguous.get(field, []), raw_evidence.quote]))
            rejected.append({"field": field, "reason": "source_quote_not_unique"})
            continue
        message_index, start, end = occurrences[0]
        context = _sentence_context(messages[message_index], start, end)
        value = parse_quote_value(field, raw_evidence.quote, context)
        if value is None:
            ambiguous[field] = list(dict.fromkeys([*ambiguous.get(field, []), raw_evidence.quote]))
            rejected.append({"field": field, "reason": "source_statement_not_unambiguous"})
            continue
        accepted[field] = Evidence(value, message_index, raw_evidence.quote)
    for raw_claim in evidence_claims:
        claim = raw_claim if isinstance(raw_claim, EvidenceQuote) else EvidenceQuote.model_validate(raw_claim)
        field = _field(claim.field)
        occurrences = _occurrences(messages, claim.quote)
        if len(occurrences) != 1:
            rejected.append({"field": field, "reason": "quote_not_unique_in_student_messages"})
            if occurrences:
                ambiguous[field] = list(dict.fromkeys([*ambiguous.get(field, []), claim.quote]))
                accepted.pop(field, None)
            continue
        message_index, start, end = occurrences[0]
        context = _sentence_context(messages[message_index], start, end)
        value = parse_quote_value(field, claim.quote, context)
        if value is None:
            rejected.append({"field": field, "reason": "quote_not_a_supported_unambiguous_statement"})
            ambiguous[field] = list(dict.fromkeys([*ambiguous.get(field, []), claim.quote]))
            accepted.pop(field, None)
            continue
        evidence = Evidence(value=value, message_index=message_index, quote=claim.quote)
        previous = accepted.get(field)
        correction = _is_explicit_correction(context)
        if previous and previous.value != value and not correction:
            ambiguous[field] = list(dict.fromkeys([previous.quote, claim.quote]))
            accepted.pop(field, None)
        elif field in ambiguous and not correction:
            ambiguous[field] = list(dict.fromkeys([*ambiguous[field], claim.quote]))
        else:
            accepted[field] = evidence
            ambiguous.pop(field, None)

    # Provider quote hints cannot hide a later conflict or correction in the
    # host-owned transcript. Resolve every supported field candidate in source
    # order, and let only an explicit, locally verified correction supersede it.
    for field in FIELDS:
        transcript_ambiguous, correction, transcript_quotes = _transcript_field_resolution(field, messages)
        if transcript_ambiguous:
            ambiguous[field] = list(dict.fromkeys([*ambiguous.get(field, []), *transcript_quotes]))
            accepted.pop(field, None)
        elif correction is not None:
            accepted[field] = correction
            ambiguous.pop(field, None)

    missing = [field for field in FIELDS if field not in accepted and field not in ambiguous]
    raw_values = {field: evidence.value for field, evidence in accepted.items()}
    payload = None
    issues: list[str] = []
    if not missing and not ambiguous:
        try:
            payload = PracticeSessionCreate.model_validate(raw_values)
        except ValidationError as exc:
            for error in exc.errors():
                field = next((part for part in error["loc"] if part in FIELDS), None)
                if field:
                    ambiguous[field] = [accepted[field].quote]
                    accepted.pop(field, None)
                else:
                    issues.append(str(error["msg"]))
            raw_values = {field: evidence.value for field, evidence in accepted.items()}
            missing = [field for field in FIELDS if field not in accepted and field not in ambiguous]

    verified_evidence = {
        field: {
            "value": evidence.value,
            "message_index": evidence.message_index,
            "quote": evidence.quote,
            "start": messages[evidence.message_index].find(evidence.quote),
            "end": messages[evidence.message_index].find(evidence.quote) + len(evidence.quote),
        }
        for field, evidence in accepted.items()
    }
    digest = preview_digest(payload, verified_evidence) if payload else None
    qs = _conversation_questions(language, missing, ambiguous)
    return {
        "status": "ready" if payload else "ambiguous" if ambiguous else "incomplete",
        "fields": payload.model_dump() if payload else raw_values,
        "verified_evidence": verified_evidence,
        "evidence_claims": [
            {"field": field, "quote": evidence.quote}
            for field, evidence in accepted.items()
        ],
        "missing": missing,
        "ambiguous": ambiguous,
        "questions": qs,
        "preview_digest": digest,
        "rejected_claims": rejected,
        "write_allowed": False,
    }


def dispatch_cli(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """The single model-callable CLI operation. It is intentionally read-only."""
    request = PrepareCommand.model_validate(envelope)
    if request.command != "study.practice.prepare":
        raise ValueError("Only study.practice.prepare is available.")
    if request.language not in {"en", "tr"}:
        raise ValueError("language must be en or tr")
    return prepare_practice(request.messages, request.language, request.evidence)


def dispatch_provider_tool(
    arguments: Mapping[str, Any], *, messages: list[str], language: str,
) -> dict[str, Any]:
    """Bind model-supplied evidence hints to host-owned transcript and locale."""
    tool_args = ProviderToolArguments.model_validate(arguments)
    return prepare_practice(messages, language, tool_args.evidence)
