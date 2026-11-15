"""AI-free benchmark for the strict, quote-grounded Study Agent CLI."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import platform
import random
import sys
import time
from pathlib import Path

from app import hamartia_cli
from app.hamartia_cli import run_json_line
from app.services import study_agent_cli, study_agent_practice

SEED = 20261115

def fixture(index: int) -> tuple[dict, dict, dict, str]:
    subjects = ("Mathematics", "Physics", "Biology", "History")
    topics = ("Functions", "Motion", "Cells", "Chronology")
    subject = subjects[index % len(subjects)]
    topic = topics[index % len(topics)]
    date = f"2026-11-{index % 28 + 1:02d}"
    correct = index % 18
    incorrect = index % 6
    blank = index % 4
    if correct + incorrect + blank == 0:
        blank = 1
    minutes = 10 + index % 70
    seconds = index % 60
    if index % 4 == 0:
        message = (
            f"I completed a practice test on {topic} in {subject} on {date}. "
            f"I got {correct} right, {incorrect} wrong, left {blank} blank; "
            f"it took {minutes} minutes and {seconds} seconds."
        )
        language = "en"
        evidence = [
            {"field": "subject", "quote": f"in {subject}"}, {"field": "topic", "quote": f"on {topic}"},
            {"field": "date", "quote": f"on {date}"}, {"field": "correct", "quote": f"{correct} right"},
            {"field": "incorrect", "quote": f"{incorrect} wrong"}, {"field": "blank", "quote": f"left {blank} blank"},
            {"field": "duration_minutes", "quote": f"{minutes} minutes"}, {"field": "duration_seconds", "quote": f"{seconds} seconds"},
        ]
    elif index % 4 == 1:
        message = (
            f"date: {date}; topic: {topic}; subject: {subject}; correct: {correct}; wrong: {incorrect}; "
            f"blank: {blank}; duration_minutes: {minutes}; duration_seconds: {seconds}"
        )
        language = "en"
        evidence = [
            {"field": "date", "quote": f"date: {date}"}, {"field": "topic", "quote": f"topic: {topic}"},
            {"field": "subject", "quote": f"subject: {subject}"}, {"field": "correct", "quote": f"correct: {correct}"},
            {"field": "incorrect", "quote": f"wrong: {incorrect}"}, {"field": "blank", "quote": f"blank: {blank}"},
            {"field": "duration_minutes", "quote": f"duration_minutes: {minutes}"},
            {"field": "duration_seconds", "quote": f"duration_seconds: {seconds}"},
        ]
    elif index % 4 == 2:
        message = (
            f"tarih: {date}; ders: {subject}; konu: {topic}; doğru: {correct}; yanlış: {incorrect}; "
            f"boş: {blank}; duration_minutes: {minutes}; duration_seconds: {seconds}"
        )
        language = "tr"
        evidence = [
            {"field": "date", "quote": f"tarih: {date}"}, {"field": "subject", "quote": f"ders: {subject}"},
            {"field": "topic", "quote": f"konu: {topic}"}, {"field": "correct", "quote": f"doğru: {correct}"},
            {"field": "incorrect", "quote": f"yanlış: {incorrect}"}, {"field": "blank", "quote": f"boş: {blank}"},
            {"field": "duration_minutes", "quote": f"duration_minutes: {minutes}"},
            {"field": "duration_seconds", "quote": f"duration_seconds: {seconds}"},
        ]
    else:
        message = (
            f"Ders {subject}. Konu {topic}. Tarih {date}. {correct} doğru, {incorrect} yanlış, "
            f"{blank} boş; {minutes} dakika ve {seconds} saniye sürdü."
        )
        language = "tr"
        evidence = [
            {"field": "subject", "quote": f"Ders {subject}"}, {"field": "topic", "quote": f"Konu {topic}"},
            {"field": "date", "quote": f"Tarih {date}"}, {"field": "correct", "quote": f"{correct} doğru"},
            {"field": "incorrect", "quote": f"{incorrect} yanlış"}, {"field": "blank", "quote": f"{blank} boş"},
            {"field": "duration_minutes", "quote": f"{minutes} dakika"}, {"field": "duration_seconds", "quote": f"{seconds} saniye"},
        ]
    request = {"command": "study.practice.prepare", "language": language, "messages": [message], "evidence": evidence}
    expected = {
        "date": date, "subject": subject, "topic": topic,
        "correct": correct, "incorrect": incorrect, "blank": blank,
        "duration_minutes": minutes, "duration_seconds": seconds,
    }
    expected_evidence = {
        item["field"]: {
            "value": expected[item["field"]], "message_index": 0, "quote": item["quote"],
            "start": message.index(item["quote"]),
            "end": message.index(item["quote"]) + len(item["quote"]),
        }
        for item in evidence
    }
    canonical = json.dumps({"fields": expected, "evidence": expected_evidence}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return request, expected, expected_evidence, expected_digest


def _assert_rejected_probe(request: dict, *, status: str, field: str | None = None, missing: bool = False) -> dict:
    result = run_json_line(json.dumps(request, ensure_ascii=False))
    _assert_exact_read_only_gate(result)
    if result.get("status") != status:
        raise AssertionError(f"expected read-only {status} result, got {result.get('status')}")
    if field:
        if missing and (field not in result.get("missing", []) or field in result.get("ambiguous", {})):
            raise AssertionError(f"{field} did not remain specifically missing")
        if not missing and (field not in result.get("ambiguous", {}) or field in result.get("missing", [])):
            raise AssertionError(f"{field} did not remain specifically ambiguous")
    return result


def _assert_exact_read_only_gate(result: dict) -> None:
    if result.get("write_allowed") is not False:
        raise AssertionError("every CLI result must explicitly set write_allowed to false")


def self_check_exact_read_only_gate() -> None:
    _assert_exact_read_only_gate({"write_allowed": False})
    for unsafe_result in ({}, {"write_allowed": None}, {"write_allowed": True}, {"write_allowed": 0}):
        try:
            _assert_exact_read_only_gate(unsafe_result)
        except AssertionError:
            continue
        raise AssertionError(f"benchmark gate accepted an unsafe value: {unsafe_result!r}")


def assert_prepare_is_structurally_side_effect_free() -> None:
    """Guard the CLI call path against provider and persistence dependencies."""
    modules = (hamartia_cli, study_agent_cli, study_agent_practice)
    forbidden_imports = ("app.services.ai_service", "app.services.storage", "openai", "httpx", "requests", "subprocess", "sqlite3")
    forbidden_calls = {"AIService", "StorageService", "create_session", "append_list", "update_list", "httpx", "requests"}
    for module in modules:
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [item.name for item in node.names]
                if any(name == forbidden or name.startswith(f"{forbidden}.") for name in imported for forbidden in forbidden_imports):
                    raise AssertionError(f"provider/storage dependency found in {module.__name__}")
            elif isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                if any(imported == forbidden or imported.startswith(f"{forbidden}.") for forbidden in forbidden_imports):
                    raise AssertionError(f"provider/storage dependency found in {module.__name__}")
            elif isinstance(node, ast.Call):
                call_name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if call_name in forbidden_calls:
                    raise AssertionError(f"provider/storage call found in {module.__name__}")


def adversarial_probes(seed: int) -> int:
    base, expected, _evidence, _digest = fixture(0)
    positives = base["evidence"]
    probes = [
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 or 7 right."], "evidence": [{"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got five or 7 right."], "evidence": [{"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["correct: 5, or 7"], "evidence": [{"field": "correct", "quote": "correct: 5, or 7"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "I got 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}, {"field": "correct", "quote": "7 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Or 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "We studied error correction, and I got 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Correction methods were reviewed; I got 7 right."] , "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Update chapter; I got 7 right."] , "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Maybe 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Perhaps 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Alternatively 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "I got 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["correct: 5 or 7"], "evidence": [{"field": "correct", "quote": "correct: 5 or 7"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or November 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 11/16/2026."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 16.11.2026."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or Nov 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or November 16th."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 2026.11.16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15 or 11/16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 16.11."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 2.03."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15, or 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15; or 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was 2026-11-15\nor 16."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 or 16:30."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "incomplete", None, False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 or 16.30."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "incomplete", None, False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["The date was November 15 or 16."], "evidence": [{"field": "date", "quote": "November 15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 15 Kasım veya 16."], "evidence": [{"field": "date", "quote": "15 Kasım"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 15 Kasım."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15.", "or the next day"], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15.", "ya da ertesi gün"], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or tomorrow."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the day after."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or the day after that."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or a day later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or one day later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or the day afterwards."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or a day afterward."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or two days later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or in 24 hours."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or next week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the following month."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or in the next week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or within two days."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or in two years."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or yesterday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the previous day."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or two weeks ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or three years before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or last week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the previous month."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 2d ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 1w before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or last Monday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or next Friday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or Monday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or this Friday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 2y ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 1yr before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 24h later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 2d later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 1w later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da yarın."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir sonraki gün."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15; ya da bir gün sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da iki gün sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da 24 saat sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da gelecek hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir sonraki hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da gelecek sene."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da iki yıl sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da dün."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir gün önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da iki hafta önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da üç yıl önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da geçen hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da geçen sene."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da geçen pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da gelecek cuma."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bu pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "ambiguous", "date", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or sixty seconds."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or half an hour."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or 1/2 hour."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 min or ½ hour."], "evidence": [{"field": "duration_minutes", "quote": "45 min"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 minutes or a half hour."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took one hour and 30 minutes."], "evidence": [{"field": "duration_minutes", "quote": "30 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 minutes plus half an hour."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["45 dakika ve yarım saat sürdü."], "evidence": [{"field": "duration_minutes", "quote": "45 dakika"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 minutes plus thirty minutes."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 seconds and thirty seconds."], "evidence": [{"field": "duration_seconds", "quote": "45 seconds"}]}, "ambiguous", "duration_seconds", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["45 dakika ve otuz dakika sürdü."], "evidence": [{"field": "duration_minutes", "quote": "45 dakika"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 minutes plus one and a half minutes."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 minutes, plus thirty minutes."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I spent 45 minutes; plus 30 minutes."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I spent 45 minutes\nplus 30 minutes."], "evidence": [{"field": "duration_minutes", "quote": "45 minutes"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["It took 45 seconds, and thirty seconds."], "evidence": [{"field": "duration_seconds", "quote": "45 seconds"}]}, "ambiguous", "duration_seconds", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["45 dakika, ve otuz dakika sürdü."], "evidence": [{"field": "duration_minutes", "quote": "45 dakika"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["45 dakika ya da bir buçuk saat sürdü."], "evidence": [{"field": "duration_minutes", "quote": "45 dakika"}]}, "ambiguous", "duration_minutes", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I practiced Functions."], "evidence": [{"field": "topic", "quote": "practiced Functions"}]}, "incomplete", "correct", True),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I practiced Functions."], "evidence": [{"field": "topic", "quote": "unquoted guess"}]}, "incomplete", "correct", True),
    ]
    for request, status, field, is_missing in probes:
        result = _assert_rejected_probe(request, status=status, field=field, missing=is_missing)
        if request["messages"] == ["I studied on 2026-11-15 or 16:30."] and (
            result.get("fields", {}).get("date") != "2026-11-15"
            or "date" in result.get("missing", [])
            or "date" in result.get("ambiguous", {})
        ):
            raise AssertionError("a time continuation was incorrectly treated as a date alternative")
        if request["messages"] == ["I studied on 2026-11-15 or 16.30."] and (
            result.get("fields", {}).get("date") != "2026-11-15"
            or "date" in result.get("missing", [])
            or "date" in result.get("ambiguous", {})
        ):
            raise AssertionError("a dotted clock time was incorrectly treated as a date alternative")

    # These transcript-boundary cases have independent full-result oracles:
    # provider hints intentionally omit the later statement, so only the host
    # transcript scan can detect the ambiguity or apply an explicit correction.
    transcript_cases = [
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Or 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["I got 5 right", "7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "We studied error correction, and I got 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["I got 5 right", "I got 7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Correction methods were reviewed; I got 7 right."] , "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["I got 5 right", "I got 7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Update chapter; I got 7 right."] , "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["I got 5 right", "I got 7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Maybe 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Perhaps 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I got 5 right.", "Alternatively 7 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "correct", ["7 right"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15.", "or the next day"], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15.", "ya da ertesi gün"], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or tomorrow."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 16.11."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "date", ["2026-11-15", "Tarih 2026-11-15"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 veya 2.03."], "evidence": [{"field": "date", "quote": "2026-11-15"}]}, "date", ["2026-11-15", "Tarih 2026-11-15"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the day after."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or the day after that."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or a day later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or one day later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or the day afterwards."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or a day afterward."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or two days later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or in 24 hours."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or next week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the following month."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or in the next week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or within two days."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or in two years."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or yesterday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the previous day."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or two weeks ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or three years before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or last week."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or the previous month."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 2d ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 1w before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or last Monday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or next Friday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or Monday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or this Friday."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 2y ago."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 1yr before."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 24h later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15 — or 2d later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I studied on 2026-11-15, or 1w later."], "evidence": [{"field": "date", "quote": "on 2026-11-15"}]}, "date", ["on 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da yarın."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir sonraki gün."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15; ya da bir gün sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da iki gün sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da 24 saat sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da gelecek hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir sonraki hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da gelecek sene."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da iki yıl sonra."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da dün."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bir gün önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da iki hafta önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da üç yıl önce."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da geçen hafta."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da geçen sene."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da geçen pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da gelecek cuma."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15, ya da pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
        ({"command": "study.practice.prepare", "language": "tr", "messages": ["Tarih 2026-11-15 — ya da bu pazartesi."], "evidence": [{"field": "date", "quote": "Tarih 2026-11-15"}]}, "date", ["Tarih 2026-11-15", "relative date continuation"]),
    ]
    all_fields = ["date", "subject", "topic", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds"]
    for request, field, expected_quotes in transcript_cases:
        result = run_json_line(json.dumps(request, ensure_ascii=False))
        _assert_exact_read_only_gate(result)
        expected_missing = [item for item in all_fields if item != field]
        if (
            result.get("status") != "ambiguous"
            or result.get("fields") != {}
            or result.get("verified_evidence") != {}
            or result.get("ambiguous") != {field: expected_quotes}
            or result.get("missing") != expected_missing
            or result.get("preview_digest") is not None
        ):
            raise AssertionError(f"transcript ambiguity did not match its full independent oracle: {result!r}")

    omitted_correction = {
        "command": "study.practice.prepare", "language": "en",
        "messages": ["I got 5 right.", "Correction: I got 7 right."],
        "evidence": [{"field": "correct", "quote": "5 right"}],
    }
    correction_result = run_json_line(json.dumps(omitted_correction, ensure_ascii=False))
    _assert_exact_read_only_gate(correction_result)
    correction_evidence = {
        "value": 7, "message_index": 1, "quote": "Correction: I got 7 right",
        "start": 0, "end": len("Correction: I got 7 right"),
    }
    if (
        correction_result.get("status") != "incomplete"
        or correction_result.get("fields", {}).get("correct") != 7
        or correction_result.get("fields") != {"correct": 7}
        or "correct" in correction_result.get("ambiguous", {})
        or correction_result.get("ambiguous") != {}
        or correction_result.get("missing") != ["date", "subject", "topic", "incorrect", "blank", "duration_minutes", "duration_seconds"]
        or correction_result.get("verified_evidence", {}).get("correct") != correction_evidence
        or correction_result.get("verified_evidence") != {"correct": correction_evidence}
        or correction_result.get("preview_digest") is not None
    ):
        raise AssertionError("host transcript correction did not override stale provider evidence exactly")

    for correction_text, correction_quote in (
        ("I got 5 right, actually I got 7 right.", "actually I got 7 right"),
        ("I got 5 right — Correction: I got 7 right.", "Correction: I got 7 right"),
    ):
        request = {
            "command": "study.practice.prepare", "language": "en", "messages": [correction_text],
            "evidence": [{"field": "correct", "quote": "5 right"}],
        }
        result = run_json_line(json.dumps(request, ensure_ascii=False))
        _assert_exact_read_only_gate(result)
        correction_evidence = {
            "value": 7, "message_index": 0, "quote": correction_quote,
            "start": correction_text.index(correction_quote),
            "end": correction_text.index(correction_quote) + len(correction_quote),
        }
        if (
            result.get("status") != "incomplete"
            or result.get("fields") != {"correct": 7}
            or result.get("verified_evidence") != {"correct": correction_evidence}
            or result.get("ambiguous") != {}
            or result.get("missing") != ["date", "subject", "topic", "incorrect", "blank", "duration_minutes", "duration_seconds"]
            or result.get("preview_digest") is not None
        ):
            raise AssertionError(f"inline correction did not replace stale evidence exactly: {result!r}")

    corrected_relative_date = {
        "command": "study.practice.prepare", "language": "en",
        "messages": ["I studied on 2026-11-15 or tomorrow.", "Correction: I studied on 2026-11-16."],
        "evidence": [{"field": "date", "quote": "on 2026-11-15"}],
    }
    corrected_date_result = run_json_line(json.dumps(corrected_relative_date, ensure_ascii=False))
    _assert_exact_read_only_gate(corrected_date_result)
    exact_date_evidence = {
        "value": "2026-11-16", "message_index": 1, "quote": "Correction: I studied on 2026-11-16",
        "start": 0, "end": len("Correction: I studied on 2026-11-16"),
    }
    if (
        corrected_date_result.get("status") != "incomplete"
        or corrected_date_result.get("fields") != {"date": "2026-11-16"}
        or corrected_date_result.get("verified_evidence") != {"date": exact_date_evidence}
        or corrected_date_result.get("ambiguous") != {}
        or corrected_date_result.get("missing") != ["subject", "topic", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds"]
        or corrected_date_result.get("preview_digest") is not None
    ):
        raise AssertionError(f"later explicit date correction did not clear relative-date ambiguity: {corrected_date_result!r}")

    # A correction is the one allowed resolution of conflicting user turns.
    correction = {**base, "messages": [*base["messages"], "Correction: I got 3 right."]}
    correction["evidence"] = [item for item in positives if item["field"] != "correct"] + [
        {"field": "correct", "quote": positives[[item["field"] for item in positives].index("correct")]["quote"]},
        {"field": "correct", "quote": "Correction: I got 3 right"},
    ]
    corrected = run_json_line(json.dumps(correction, ensure_ascii=False))
    _assert_exact_read_only_gate(corrected)
    expected_corrected = {**expected, "correct": 3}
    expected_evidence = {
        item["field"]: {
            "value": expected_corrected[item["field"]],
            "message_index": 1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0,
            "quote": item["quote"],
            "start": correction["messages"][1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0].index(item["quote"]),
            "end": correction["messages"][1 if item["field"] == "correct" and item["quote"].startswith("Correction") else 0].index(item["quote"]) + len(item["quote"]),
        }
        for item in correction["evidence"] if not (item["field"] == "correct" and not item["quote"].startswith("Correction"))
    }
    corrected_digest = hashlib.sha256(json.dumps({"fields": expected_corrected, "evidence": expected_evidence}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if corrected.get("status") != "ready" or corrected.get("fields") != expected_corrected or corrected.get("verified_evidence") != expected_evidence or corrected.get("preview_digest") != corrected_digest:
        raise AssertionError("explicit correction did not resolve the transcript to the independent corrected oracle")
    return len(probes) + len(transcript_cases) + 5


def run_trial(count: int, seed: int) -> dict:
    self_check_exact_read_only_gate()
    assert_prepare_is_structurally_side_effect_free()
    rng = random.Random(seed)
    fixtures = [fixture(index) for index in range(count)]
    rng.shuffle(fixtures)
    encoded = [json.dumps(request, ensure_ascii=False, separators=(",", ":")) for request, _, _, _ in fixtures]
    started = time.perf_counter()
    for index, (line, (_, expected, expected_evidence, expected_digest)) in enumerate(zip(encoded, fixtures, strict=True)):
        result = run_json_line(line)
        _assert_exact_read_only_gate(result)
        if result.get("status") != "ready" or result.get("fields") != expected:
            raise AssertionError(f"independent CLI oracle mismatch at row {index}")
        if result.get("preview_digest") != expected_digest:
            raise AssertionError(f"independent exact-preview digest mismatch at row {index}")
        if result.get("verified_evidence") != expected_evidence:
            raise AssertionError(f"independent quote/value/offset oracle mismatch at row {index}")
    elapsed = time.perf_counter() - started

    negatives = [
        ({"command": "study.practice.prepare", "language": "en", "messages": ["I did not get 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "study.practice.prepare", "language": "en", "messages": ["Maybe I got about 5 right."], "evidence": [{"field": "correct", "quote": "5 right"}]}, "ambiguous", "correct", False),
        ({"command": "practice.delete", "language": "en", "messages": ["delete"], "evidence": []}, "error", None, False),
    ]
    for request, status, field, missing in negatives:
        _assert_rejected_probe(request, status=status, field=field, missing=missing)
    adversarial_count = adversarial_probes(seed)
    return {
        "records_checked": count, "seconds": elapsed, "probes_checked": len(negatives) + adversarial_count,
        "side_effects": {
            "provider_calls": {"measurement": "structurally_excluded", "runtime_counted": False},
            "writes": {"measurement": "structurally_excluded", "runtime_counted": False},
        },
    }


def main(repeats: int = 5, json_output: str | None = None) -> None:
    if not 3 <= repeats <= 15:
        raise ValueError("repeats must be between 3 and 15")
    runs = []
    for count in (24, 100):
        run_trial(count, SEED)  # warm-up
        results = [run_trial(count, SEED) for _ in range(repeats)]
        durations = sorted(result["seconds"] for result in results)
        runs.append({
            **results[-1], "p50_seconds": round(durations[len(durations) // 2], 6),
            "p95_seconds": round(durations[-1], 6),
            "oracle": "EN natural/labeled and TR natural/labeled fixtures; independent values/evidence/digests; adversarial exact statuses and corrections",
            "side_effect_check": "AST inspection confirmed CLI/prepare modules import and call no provider or persistence services; counters are structural exclusions, not runtime instrumentation",
        })
    output = {
        "benchmark": "study_agent_cli_prepare", "seed": SEED, "ai_included": False,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "logical_cpus": __import__("os").cpu_count()},
        "runs": runs,
    }
    serialized = json.dumps(output, ensure_ascii=False, indent=2)
    if json_output:
        Path(json_output).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json-output")
    args = parser.parse_args()
    main(args.repeats, args.json_output)
