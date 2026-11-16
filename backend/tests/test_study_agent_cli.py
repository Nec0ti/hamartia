import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.hamartia_cli import MAX_LINE_LENGTH, run_json_line
from app.services.study_agent_cli import EvidenceQuote, ProviderToolArguments, dispatch_cli, dispatch_provider_tool, parse_quote_value, prepare_practice, provider_tool_parameters
from app.services.study_agent_practice import extract_fields
from app.services.storage import StorageService
from app.models.schemas import Exam, LearningEvidence, PracticeSession, Question

BACKEND_DIR = Path(__file__).resolve().parents[1]


MESSAGES = [
    "I completed a practice test on Functions in Mathematics on 2026-11-15. "
    "I got 12 right, 3 wrong, left 1 blank; it took 45 minutes and 0 seconds."
]
CLAIMS = [
    {"field": "subject", "quote": "in Mathematics"},
    {"field": "topic", "quote": "on Functions"},
    {"field": "date", "quote": "on 2026-11-15"},
    {"field": "correct", "quote": "12 right"},
    {"field": "incorrect", "quote": "3 wrong"},
    {"field": "blank", "quote": "left 1 blank"},
    {"field": "duration_minutes", "quote": "it took 45 minutes"},
    {"field": "duration_seconds", "quote": "0 seconds"},
]


class StudyAgentCliTests(unittest.TestCase):
    def test_provider_tool_schema_is_strict_and_accepts_only_evidence_quotes(self):
        schema = provider_tool_parameters()
        self.assertEqual(schema["required"], ["evidence"])
        self.assertIs(schema["additionalProperties"], False)
        evidence = schema["properties"]["evidence"]
        self.assertEqual(evidence["items"]["required"], ["field", "quote"])
        self.assertIs(evidence["items"]["additionalProperties"], False)
        self.assertEqual(set(evidence["items"]["properties"]), {"field", "quote"})
        self.assertEqual(set(schema["properties"]), {"evidence"})

    def test_natural_language_quotes_are_bound_to_source_and_return_ready_preview(self):
        result = prepare_practice(MESSAGES, "en", CLAIMS)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["write_allowed"])
        self.assertEqual(result["fields"], {
            "date": "2026-11-15", "subject": "Mathematics", "topic": "Functions",
            "correct": 12, "incorrect": 3, "blank": 1,
            "duration_minutes": 45, "duration_seconds": 0,
        })
        self.assertEqual(result["verified_evidence"]["correct"]["quote"], "12 right")
        self.assertEqual(result["verified_evidence"]["correct"]["start"], MESSAGES[0].index("12 right"))
        canonical = {
            "fields": {
                **result["fields"], "scoring_profile_id": None, "scoring_profile_version": None,
            },
            "evidence": result["verified_evidence"],
            "scoring_profile": {
                "profile_id": "legacy-yks", "version": 1, "display_name": "YKS (legacy)",
                "country_label": "Türkiye", "scoring_rule": {
                    "correct_points": "1/1", "wrong_penalty": "1/4", "blank_points": "0/1",
                },
            },
        }
        expected_digest = hashlib.sha256(json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        self.assertEqual(result["preview_digest"], expected_digest)

    def test_turkish_natural_phrases_are_parsed_and_questions_follow_saved_language(self):
        message = "Matematik dersinde Fonksiyon çalıştım; 12 doğru, 3 yanlış, 1 boş yaptım. 45 dakika ve 10 saniye sürdü. Tarih 2026-11-15."
        claims = [
            {"field": "subject", "quote": "Matematik dersinde"},
            {"field": "topic", "quote": "dersinde Fonksiyon çalıştım"},
            {"field": "correct", "quote": "12 doğru"},
            {"field": "incorrect", "quote": "3 yanlış"},
            {"field": "blank", "quote": "1 boş"},
            {"field": "duration_minutes", "quote": "45 dakika"},
            {"field": "duration_seconds", "quote": "10 saniye"},
            {"field": "date", "quote": "Tarih 2026-11-15"},
        ]
        result = prepare_practice([message], "tr", claims)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fields"]["subject"], "Matematik")
        self.assertEqual(result["fields"]["topic"], "Fonksiyon")
        incomplete = prepare_practice(["Dün Matematik çalıştım."], "tr", [])
        self.assertIn("Hangi konuda çalıştın?", incomplete["questions"])

    def test_quote_alone_does_not_override_negation_hedge_hypothetical_or_reported_context(self):
        cases = [
            ("I did not get 5 right.", "5 right"),
            ("Maybe I got about 5 right.", "5 right"),
            ("If I got 5 right, I would be happy.", "5 right"),
            ("My teacher said I got 5 right.", "5 right"),
            ("Could I have got 5 right?", "5 right"),
            ("Did I get 5 right", "5 right"),
            ("5 doğru mu", "5 doğru mu"),
        ]
        for message, quote in cases:
            with self.subTest(message=message):
                language = "tr" if "doğru" in message else "en"
                result = prepare_practice([message], language, [{"field": "correct", "quote": quote}])
                self.assertNotIn("correct", result["fields"])
                self.assertIn("correct", result["ambiguous"])
                self.assertEqual(result["status"], "ambiguous")

    def test_field_semantics_and_number_boundaries_are_verified(self):
        cases = [
            ("correct", "I got 12 wrong.", "12"),
            ("incorrect", "I got 12 right.", "12"),
            ("correct", "I got 12 right.", "2"),
            ("correct", "My net is 12.", "12"),
            ("correct", "I got 7 of 10.", "7 of 10"),
            ("correct", "I got -5 right.", "5 right"),
            ("correct", "I got 1.5 right.", "5 right"),
            ("correct", "I got 1,200 right.", "200 right"),
        ]
        for field, message, quote in cases:
            with self.subTest(field=field, message=message, quote=quote):
                self.assertIsNone(parse_quote_value(field, quote, message))
        self.assertIsNone(parse_quote_value("correct", "correct: 1.5", "correct: 1.5"))
        self.assertIsNone(parse_quote_value("duration_minutes", "duration_minutes: 1.5", "duration_minutes: 1.5"))
        for field, text in (
            ("correct", "correct: 1.5"),
            ("duration_minutes", "duration_minutes: 1.5"),
            ("correct", "correct: -5"),
            ("correct", "correct: 1,200"),
            ("correct", "correct: 1 200"),
            ("correct", "correct: 5 or 7"),
            ("correct", "correct: five or 7"),
            ("correct", "correct: 5, or 7"),
        ):
            with self.subTest(field=field, text=text):
                accepted, _ambiguous = extract_fields([text])
                self.assertNotIn(field, accepted)

    def test_quote_cannot_cherry_pick_one_value_from_sentence_alternatives(self):
        count_message = "I got 5 right and 7 right."
        for quote in ("5 right", "7 right"):
            with self.subTest(quote=quote):
                result = prepare_practice([count_message], "en", [{"field": "correct", "quote": quote}])
                self.assertNotIn("correct", result["fields"])
                self.assertIn("correct", result["ambiguous"])

        topic_message = "I worked on Functions or Geometry."
        result = prepare_practice([topic_message], "en", [{"field": "topic", "quote": "worked on Functions"}])
        self.assertNotIn("topic", result["fields"])
        self.assertIn("topic", result["ambiguous"])

    def test_range_and_date_alternatives_cannot_be_cherry_picked(self):
        cases = [
            ("I got 5 or 7 right.", "5 or 7 right", "en"),
            ("I got 5 or 7 right.", "7 right", "en"),
            ("I got between 5 and 7 right.", "7 right", "en"),
            ("5 veya 7 doğru yaptım.", "7 doğru", "tr"),
            ("I got five or 7 right.", "7 right", "en"),
            ("Beş veya 7 doğru yaptım.", "7 doğru", "tr"),
            ("Correct: 5, or 7", "Correct: 5, or 7", "en"),
            ("I got 5 right; correct: 5 or 7", "correct: 5", "en"),
        ]
        for message, quote, language in cases:
            with self.subTest(message=message, quote=quote):
                result = prepare_practice([message], language, [{"field": "correct", "quote": quote}])
                self.assertNotIn("correct", result["fields"])
                self.assertIn("correct", result["ambiguous"])
        date_message = "The date was 2026-11-15 or 2026-11-16."
        date_result = prepare_practice([date_message], "en", [{"field": "date", "quote": "2026-11-15"}])
        self.assertNotIn("date", date_result["fields"])
        self.assertIn("date", date_result["ambiguous"])
        mixed_date = "The date was 2026-11-15 or November 16."
        mixed_result = prepare_practice([mixed_date], "en", [{"field": "date", "quote": "2026-11-15"}])
        self.assertNotIn("date", mixed_result["fields"])
        self.assertIn("date", mixed_result["ambiguous"])
        for statement, quote in (
            ("The date was 2026-11-15 or 11/16/2026.", "2026-11-15"),
            ("The date was 2026-11-15 or 2026/11/16.", "2026-11-15"),
            ("The date was 2026-11-15 or 16.11.2026.", "2026-11-15"),
            ("The date was 2026-11-15 or 16-11-2026.", "2026-11-15"),
            ("The date was 2026-11-15 or Nov 16.", "2026-11-15"),
            ("The date was 2026-11-15 or November 16th.", "2026-11-15"),
            ("The date was 2026-11-15 or 2026.11.16.", "2026-11-15"),
            ("The date was 2026-11-15 or 11/16.", "2026-11-15"),
            ("The date was 2026-11-15 or 16.11.", "2026-11-15"),
            ("The date was 2026-11-15 or 2.03.", "2026-11-15"),
            ("The date was 2026-11-15 or 11.16.", "2026-11-15"),
            ("The date was 2026-11-15, or 16.", "2026-11-15"),
            ("The date was 2026-11-15; or 16.", "2026-11-15"),
            ("The date was 2026-11-15\nor 16.", "2026-11-15"),
            ("The date was November 15 or 16.", "November 15"),
            ("Tarih 15 Kasım veya 16.", "15 Kasım"),
            ("Tarih 2026-11-15 veya 15 Kasım.", "2026-11-15"),
        ):
            with self.subTest(statement=statement):
                result = prepare_practice([statement], "tr" if statement.startswith("Tarih") else "en", [{"field": "date", "quote": quote}])
                self.assertNotIn("date", result["fields"])
                self.assertIn("date", result["ambiguous"])
        time_text = "I studied on 2026-11-15 or 16:30."
        self.assertEqual(parse_quote_value("date", "on 2026-11-15", time_text), "2026-11-15")
        dotted_time_text = "I studied on 2026-11-15 or 16.30."
        self.assertEqual(parse_quote_value("date", "on 2026-11-15", dotted_time_text), "2026-11-15")
        dotted_time_result = prepare_practice([dotted_time_text], "en", [{"field": "date", "quote": "on 2026-11-15"}])
        self.assertEqual(dotted_time_result["fields"]["date"], "2026-11-15")
        self.assertNotIn("date", dotted_time_result["ambiguous"])
        for dotted_clock in ("I studied on 2026-11-15 or 16.00.", "I studied on 2026-11-15 or 12.00."):
            with self.subTest(dotted_clock=dotted_clock):
                result = prepare_practice([dotted_clock], "en", [{"field": "date", "quote": "on 2026-11-15"}])
                self.assertEqual(result["fields"]["date"], "2026-11-15")
                self.assertNotIn("date", result["ambiguous"])

    def test_duration_alternatives_accept_only_neither_candidate(self):
        for field, context, quote in (
            ("duration_minutes", "It took 45 min or an hour.", "45 min"),
            ("duration_minutes", "45 dakika ya da bir saat sürdü.", "45 dakika"),
            ("duration_minutes", "It took 45 min or sixty seconds.", "45 min"),
            ("duration_minutes", "It took 45 min or half an hour.", "45 min"),
            ("duration_minutes", "45 dakika ya da bir buçuk saat sürdü.", "45 dakika"),
            ("duration_minutes", "It took 45 min or 1.5 minutes.", "45 min"),
            ("duration_seconds", "It took 45 sec or 1.5 seconds.", "45 sec"),
            ("duration_minutes", "It took 45 min or 1/2 hour.", "45 min"),
            ("duration_minutes", "It took 45 min or ½ hour.", "45 min"),
            ("duration_minutes", "It took 45 minutes or a half hour.", "45 minutes"),
            ("duration_minutes", "It took one hour and 30 minutes.", "30 minutes"),
            ("duration_minutes", "It took 45 minutes plus half an hour.", "45 minutes"),
            ("duration_minutes", "45 dakika ve yarım saat sürdü.", "45 dakika"),
            ("duration_minutes", "It took 45 minutes plus thirty minutes.", "45 minutes"),
            ("duration_seconds", "It took 45 seconds and thirty seconds.", "45 seconds"),
            ("duration_minutes", "45 dakika ve otuz dakika sürdü.", "45 dakika"),
            ("duration_minutes", "It took 45 minutes plus one and a half minutes.", "45 minutes"),
            ("duration_minutes", "It took 45 minutes, plus thirty minutes.", "45 minutes"),
            ("duration_seconds", "It took 45 seconds, and thirty seconds.", "45 seconds"),
            ("duration_minutes", "45 dakika, ve otuz dakika sürdü.", "45 dakika"),
        ):
            with self.subTest(context=context):
                self.assertIsNone(parse_quote_value(field, quote, context))

        for message, field, quote in (
            ("I spent 45 minutes; plus 30 minutes.", "duration_minutes", "45 minutes"),
            ("I spent 45 minutes\nplus 30 minutes.", "duration_minutes", "45 minutes"),
            ("The date was 2026-11-15; or 16.", "date", "2026-11-15"),
            ("The date was 2026-11-15\nor 16.", "date", "2026-11-15"),
        ):
            with self.subTest(message=message):
                result = prepare_practice([message], "en", [{"field": field, "quote": quote}])
                self.assertIn(field, result["ambiguous"])

    def test_ambiguous_topics_dates_and_durations_are_not_guessed(self):
        self.assertIsNone(parse_quote_value("topic", "I practiced Functions and Geometry."))
        self.assertIsNone(parse_quote_value("date", "today"))
        self.assertIsNone(parse_quote_value("date", "on 11/15/2026"))
        self.assertIsNone(parse_quote_value("duration_minutes", "about 45 minutes"))
        self.assertIsNone(parse_quote_value("duration_minutes", "1:30"))
        self.assertIsNone(parse_quote_value("duration_minutes", "30 minutes", "It took 1 hour 30 minutes."))
        self.assertIsNone(parse_quote_value("duration_minutes", "45 minutes", "It took 45 minutes or 1 hour."))
        self.assertIsNone(parse_quote_value("duration_minutes", "45 minutes", "It took 45 minutes or 60 seconds."))
        result = prepare_practice(["Today I practiced Functions."], "en", [{"field": "date", "quote": "Today"}])
        self.assertIn("date", result["ambiguous"])
        self.assertFalse(result["write_allowed"])

    def test_zero_is_explicit_and_not_confused_with_a_missing_count(self):
        result = prepare_practice(["I got 0 right."], "en", [{"field": "correct", "quote": "0 right"}])
        self.assertEqual(result["fields"]["correct"], 0)
        self.assertNotIn("correct", result["missing"])

    def test_conflicting_turns_require_an_explicit_correction(self):
        messages = ["I got 5 right.", "I got 7 right."]
        result = prepare_practice(messages, "en", [
            {"field": "correct", "quote": "5 right"},
            {"field": "correct", "quote": "7 right"},
        ])
        self.assertIn("correct", result["ambiguous"])
        corrected = prepare_practice(
            [*messages, "Correction: I got 7 right."], "en",
            [{"field": "correct", "quote": "5 right"}, {"field": "correct", "quote": "Correction: I got 7 right."}],
        )
        self.assertEqual(corrected["fields"]["correct"], 7)
        self.assertNotIn("correct", corrected["ambiguous"])
        punctuated_correction = prepare_practice(
            ["I got 5 right; Correction: I got 7 right."], "en",
            [
                {"field": "correct", "quote": "5 right"},
                {"field": "correct", "quote": "Correction: I got 7 right"},
            ],
        )
        self.assertEqual(punctuated_correction["fields"]["correct"], 7)
        self.assertNotIn("correct", punctuated_correction["ambiguous"])
        omitted_conflict_hint = prepare_practice(
            ["I got 5 right.", "Or 7 right."], "en",
            [{"field": "correct", "quote": "5 right"}],
        )
        self.assertNotIn("correct", omitted_conflict_hint["fields"])
        self.assertIn("correct", omitted_conflict_hint["ambiguous"])
        for ordinary_phrase in (
            "We studied error correction, and I got 7 right.",
            "Correction methods were reviewed; I got 7 right.",
            "Update chapter; I got 7 right.",
        ):
            with self.subTest(ordinary_phrase=ordinary_phrase):
                ordinary_correction_phrase = prepare_practice(
                    ["I got 5 right.", ordinary_phrase], "en",
                    [{"field": "correct", "quote": "5 right"}],
                )
                self.assertEqual(ordinary_correction_phrase["status"], "ambiguous")
                self.assertEqual(ordinary_correction_phrase["ambiguous"]["correct"], ["I got 5 right", "I got 7 right"])
        omitted_correction_hint = prepare_practice(
            ["I got 5 right.", "Correction: I got 7 right."], "en",
            [{"field": "correct", "quote": "5 right"}],
        )
        self.assertEqual(omitted_correction_hint["fields"]["correct"], 7)
        self.assertEqual(omitted_correction_hint["verified_evidence"]["correct"]["message_index"], 1)
        self.assertEqual(omitted_correction_hint["verified_evidence"]["correct"]["quote"], "Correction: I got 7 right")
        joined_correction = prepare_practice(
            ["I got 5 right; and Correction: I got 7 right."], "en",
            [{"field": "correct", "quote": "5 right"}],
        )
        self.assertEqual(joined_correction["fields"]["correct"], 7)
        self.assertEqual(joined_correction["verified_evidence"]["correct"]["quote"], "and Correction: I got 7 right")
        for message, expected_quote in (
            ("I got 5 right, actually I got 7 right.", "actually I got 7 right"),
            ("I got 5 right — Correction: I got 7 right.", "Correction: I got 7 right"),
        ):
            with self.subTest(message=message):
                result = prepare_practice([message], "en", [{"field": "correct", "quote": "5 right"}])
                self.assertEqual(result["fields"]["correct"], 7)
                self.assertNotIn("correct", result["ambiguous"])
                self.assertEqual(result["verified_evidence"]["correct"]["quote"], expected_quote)
        for later in ("Maybe 7 right.", "Perhaps 7 right.", "Alternatively 7 right."):
            with self.subTest(later=later):
                result = prepare_practice(["I got 5 right.", later], "en", [{"field": "correct", "quote": "5 right"}])
                self.assertIn("correct", result["ambiguous"])
        relative_date_cases = (
            ("I studied on 2026-11-15, or tomorrow.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or the day after.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or the day after that.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or a day later.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or one day later.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or the day afterwards.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or a day afterward.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or two days later.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or in 24 hours.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or next week.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or the following month.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or in the next week.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or within two days.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or in two years.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or yesterday.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or the previous day.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or two weeks ago.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or three years before.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or last week.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or the previous month.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or 2d ago.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or 1w before.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or last Monday.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or next Friday.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or Monday.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or this Friday.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or 2y ago.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or 1yr before.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or 24h later.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15 — or 2d later.", "en", "on 2026-11-15"),
            ("I studied on 2026-11-15, or 1w later.", "en", "on 2026-11-15"),
            ("Tarih 2026-11-15, ya da yarın.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da bir sonraki gün.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15; ya da bir gün sonra.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da iki gün sonra.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da 24 saat sonra.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da gelecek hafta.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da bir sonraki hafta.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da gelecek sene.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da iki yıl sonra.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da dün.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da bir gün önce.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da iki hafta önce.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da üç yıl önce.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da geçen hafta.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da geçen sene.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da geçen pazartesi.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da gelecek cuma.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15, ya da pazartesi.", "tr", "Tarih 2026-11-15"),
            ("Tarih 2026-11-15 — ya da bu pazartesi.", "tr", "Tarih 2026-11-15"),
            ("I studied on 2026-11-15.\nor the next day.", "en", "on 2026-11-15"),
        )
        for message, language, quote in relative_date_cases:
            with self.subTest(message=message):
                result = prepare_practice([message], language, [{"field": "date", "quote": quote}])
                self.assertEqual(result["status"], "ambiguous")
                self.assertIn("date", result["ambiguous"])
                self.assertFalse(result["write_allowed"])
        corrected_relative_date = prepare_practice(
            ["I studied on 2026-11-15 or tomorrow.", "Correction: I studied on 2026-11-16."], "en",
            [{"field": "date", "quote": "on 2026-11-15"}],
        )
        self.assertEqual(corrected_relative_date["fields"]["date"], "2026-11-16")
        self.assertNotIn("date", corrected_relative_date["ambiguous"])
        self.assertEqual(corrected_relative_date["verified_evidence"]["date"]["quote"], "Correction: I studied on 2026-11-16")
        unrelated_clause = prepare_practice(
            ["I got 5 right; I practiced Functions."], "en",
            [{"field": "correct", "quote": "5 right"}],
        )
        self.assertEqual(unrelated_clause["fields"]["correct"], 5)
        self.assertNotIn("correct", unrelated_clause["ambiguous"])

    def test_duplicate_or_unicode_mismatched_quotes_are_rejected(self):
        repeated = prepare_practice(["I got 5 right.", "I got 5 right."], "en", [{"field": "correct", "quote": "5 right"}])
        self.assertIn("correct", repeated["ambiguous"])
        mismatched = prepare_practice(["5 dogru yaptım."], "tr", [{"field": "correct", "quote": "5 doğru"}])
        self.assertNotIn("correct", mismatched["fields"])
        self.assertIn("correct", mismatched["missing"])

    def test_tool_schema_rejects_injected_fields_indexes_and_paths(self):
        for claim in (
            {"field": "correct", "quote": "5 right", "message_index": 99},
            {"field": "correct", "quote": "5 right", "value": 5},
            {"field": "delete_record", "quote": "5 right"},
            {"field": "correct", "quote": "5 right", "path": "/tmp/user-data"},
        ):
            with self.subTest(claim=claim), self.assertRaises(ValidationError):
                EvidenceQuote.model_validate(claim)

    def test_provider_tool_arguments_never_choose_transcript_or_language(self):
        with self.assertRaises(ValidationError):
            ProviderToolArguments.model_validate({
                "evidence": [{"field": "correct", "quote": "9 right"}],
                "messages": ["I got 9 right."],
            })
        with self.assertRaises(ValidationError):
            ProviderToolArguments.model_validate({
                "evidence": [{"field": "correct", "quote": "5 right"}],
                "language": "en",
            })
        with self.assertRaises(ValidationError):
            ProviderToolArguments.model_validate({
                "evidence": [{"field": "correct", "quote": "5 right"}],
                "message_index": 99,
            })
        result = dispatch_provider_tool(
            {"evidence": [{"field": "correct", "quote": "5 right"}]},
            messages=["I got 5 right."], language="tr",
        )
        self.assertEqual(result["fields"]["correct"], 5)
        fabricated = dispatch_provider_tool(
            {"evidence": [{"field": "correct", "quote": "9 right"}]},
            messages=["I got 5 right."], language="en",
        )
        self.assertNotIn("correct", fabricated["fields"])

    def test_legacy_read_only_practice_prepare_command_stays_supported(self):
        request = {
            "command": "study.practice.prepare", "language": "en",
            "messages": MESSAGES, "evidence": CLAIMS,
        }
        result = run_json_line(json.dumps(request))
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["write_allowed"])
        self.assertEqual(run_json_line('{"command":"practice.delete","language":"en","messages":["x"]}')["status"], "error")
        self.assertEqual(run_json_line('{"command":"study.practice.prepare","command":"practice.delete"}')["status"], "error")
        self.assertEqual(run_json_line("[]")["status"], "error")

    def test_cli_module_runs_as_a_json_lines_process(self):
        request = {"command": "study.practice.prepare", "language": "en", "messages": MESSAGES, "evidence": CLAIMS}
        process = subprocess.run(
            [sys.executable, "-m", "app.hamartia_cli", "--jsonl"],
            input=json.dumps(request) + "\n", text=True, capture_output=True,
            cwd=BACKEND_DIR, check=True, timeout=30,
        )
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["write_allowed"])

    def test_cli_process_bounds_and_drains_oversized_lines(self):
        request = {"command": "study.practice.prepare", "language": "en", "messages": MESSAGES, "evidence": CLAIMS}
        process = subprocess.run(
            [sys.executable, "-m", "app.hamartia_cli", "--jsonl"],
            input='{"padding":"' + ("x" * MAX_LINE_LENGTH) + '"}\n' + json.dumps(request) + "\n",
            text=True, capture_output=True, cwd=BACKEND_DIR, check=True, timeout=30,
        )
        lines = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(lines[0], {"status": "error", "error": "request_too_large", "write_allowed": False})
        self.assertEqual(lines[1]["status"], "ready")

    def test_cli_rejects_oversized_envelope_without_processing(self):
        result = run_json_line('{"payload":"' + ("x" * MAX_LINE_LENGTH) + '"}')
        self.assertEqual(result, {"status": "error", "error": "request_too_large", "write_allowed": False})

    def test_tool_has_no_write_capability(self):
        result = dispatch_cli({"command": "study.practice.prepare", "language": "en", "messages": ["hello"], "evidence": []})
        self.assertNotIn("create", result)
        self.assertNotIn("write", result)
        self.assertFalse(result["write_allowed"])

    def test_jsonl_host_workflows_preview_before_explicit_approval_and_replay_once(self):
        from contextlib import ExitStack

        from app.core import config
        from app.models.schemas import legacy_yks_profile
        from app.services.ai_service import AIService

        temporary = tempfile.TemporaryDirectory()
        data_dir = Path(temporary.name)
        storage = StorageService(data_dir)
        self.addCleanup(temporary.cleanup)

        def invoke(command, **body):
            return run_json_line(json.dumps({"command": command, **body}))

        def approve(command, draft, conversation, extras=None):
            body = {key: value for key, value in draft.items() if key in {
                "messages", "language", "evidence_claims", "fields",
                "preview_digest", "scoring_profile_id", "scoring_profile_version",
                "scoring_profile_snapshot", "derived", "expected_exam_field", "state_token",
                "expected_question_field", "expected_evidence_field",
            }}
            body["evidence"] = draft.get("verified_evidence", draft.get("evidence"))
            body["approval_id"] = str(uuid.uuid4())
            body["approved"] = True
            body.update(conversation)
            body.update(extras or {})
            first = invoke(command, **body)
            retry = invoke(command, **body)
            self.assertEqual(first["status"], "saved", first)
            self.assertEqual(retry, first)
            return first["record"]

        provider_methods = (
            "study_chat", "study_practice_prepare", "study_learning_evidence_prepare",
            "study_question_prepare", "study_exam_prepare", "study_sectioned_exam_prepare",
        )
        with patch.object(config, "DATA_DIR", data_dir), ExitStack() as stack:
            trips = [stack.enter_context(patch.object(AIService, name, side_effect=AssertionError("provider call"))) for name in provider_methods]

            practice = invoke("study.practice.draft", messages=MESSAGES, language="en", evidence_claims=CLAIMS)
            self.assertEqual(practice["status"], "ready")
            self.assertFalse(practice["write_allowed"])
            self.assertEqual(storage.load_list("practice_sessions.json", PracticeSession), [])
            saved_practice = approve("study.practice.approve", practice, {"messages": MESSAGES, "language": "en"})
            self.assertEqual(saved_practice["scoring_profile"]["profile_id"], "legacy-yks")
            self.assertEqual(len(storage.load_list("practice_sessions.json", PracticeSession)), 1)

            learning_messages = ["I completed reading chapter 2 and made notes.", "Biology", "Cell division", "2026-11-16", "Comparing diagrams made the stages easier to distinguish."]
            learning_claims = [{"field": field, "quote": quote} for field, quote in zip(
                ("activity", "subject", "topic", "date", "observation"), learning_messages, strict=True,
            )]
            learning = invoke("study.learning_evidence.draft", messages=learning_messages, language="en", evidence_claims=learning_claims)
            self.assertEqual(learning["status"], "ready")
            self.assertEqual(learning["questions"], [])
            self.assertEqual(storage.load_list("learning_evidence.json", LearningEvidence), [])
            approve("study.learning_evidence.approve", learning, {"messages": learning_messages, "language": "en"})
            self.assertEqual(len(storage.load_list("learning_evidence.json", LearningEvidence)), 1)

            question_messages = ["If a rectangle has width 4 cm and length 7 cm, what is its area?", "Biology", "Geometry"]
            question_claims = [{"field": field, "quote": quote} for field, quote in zip(
                ("question_text", "subject", "topic"), question_messages, strict=True,
            )]
            question = None
            token = None
            for index, (field, quote) in enumerate(zip(("question_text", "subject", "topic"), question_messages, strict=True)):
                question = invoke("study.question.draft", messages=question_messages[:index + 1], language="en",
                                  expected_question_field=field, state_token=token,
                                  evidence_claims=[{"field": field, "quote": quote}])
                self.assertIn(question["status"], {"incomplete", "ready"})
                token = question.get("state_token")
            self.assertEqual(question["status"], "ready")
            self.assertEqual(storage.load_list("questions.json", Question), [])
            approve("study.question.approve", question,
                    {"messages": question_messages, "language": "en"})
            self.assertEqual(len(storage.load_list("questions.json", Question)), 1)

            profile = legacy_yks_profile()
            exam_fields = ("date", "subject", "correct", "incorrect", "blank", "duration_minutes", "duration_seconds")
            exam_values = ("2026-11-16", "Biology", "25", "3", "2", "55", "0")
            exam_messages, exam_claims, token, exam = [], [], None, None
            for field, value in zip(exam_fields, exam_values, strict=True):
                exam_messages.append(value)
                exam_claims.append({"field": field, "quote": value})
                exam = invoke("study.exam.draft", messages=exam_messages, language="en", expected_exam_field=field,
                              state_token=token, scoring_profile_id=profile.profile_id,
                              scoring_profile_version=profile.version, evidence_claims=[exam_claims[-1]])
                token = exam.get("state_token")
            self.assertEqual(exam["status"], "ready")
            self.assertEqual(storage.load_list("exams.json", Exam), [])
            approve("study.exam.approve", exam, {"messages": exam_messages, "language": "en"},
                    {"state_token": None, "expected_exam_field": "duration_seconds",
                     "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version})
            self.assertEqual(len(storage.load_list("exams.json", Exam)), 1)

            section_fields = ("exam_type", "date", "duration_minutes", "duration_seconds", "section_count",
                              "section_1_subject", "section_1_correct", "section_1_incorrect", "section_1_blank")
            section_values = ("TYT", "2026-11-16", "90", "0", "1", "Mathematics", "10", "2", "3")
            section_messages, section_claims, token, sectioned = [], [], None, None
            for field, value in zip(section_fields, section_values, strict=True):
                section_messages.append(value)
                section_claims.append({"field": field, "quote": value})
                sectioned = invoke("study.sectioned_exam.draft", messages=section_messages, language="en",
                                   expected_exam_field=field, state_token=token,
                                   scoring_profile_id=profile.profile_id, scoring_profile_version=profile.version,
                                   evidence_claims=[section_claims[-1]])
                token = sectioned.get("state_token")
            self.assertEqual(sectioned["status"], "ready")
            self.assertEqual(len(storage.load_list("exams.json", Exam)), 1)
            saved_sectioned = approve("study.sectioned_exam.approve", sectioned,
                                      {"messages": section_messages, "language": "en"},
                                      {"state_token": None, "expected_exam_field": "section_1_blank",
                                       "scoring_profile_id": profile.profile_id, "scoring_profile_version": profile.version})
            self.assertEqual(saved_sectioned["sections"][0]["subject"], "Mathematics")
            self.assertEqual(len(storage.load_list("exams.json", Exam)), 2)
            for trip in trips:
                trip.assert_not_called()

    def test_jsonl_rejects_unapproved_unknown_and_provider_value_payloads_without_writes(self):
        from app.core import config

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        data_dir = Path(temporary.name)
        with patch.object(config, "DATA_DIR", data_dir):
            base = {"messages": MESSAGES, "language": "en", "evidence_claims": CLAIMS}
            invalid = [
                {"command": "study.practice.draft", **base, "unexpected": True},
                {"command": "study.practice.draft", **base, "proposal": {"correct": 12}},
                {"command": "study.practice.approve", **base, "approved": False},
            ]
            for request in invalid:
                with self.subTest(request=request["command"]):
                    result = run_json_line(json.dumps(request))
                    self.assertEqual(result["status"], "error")
                    self.assertFalse(result["write_allowed"])
            self.assertEqual(StorageService(data_dir).load_list("practice_sessions.json", PracticeSession), [])

    def test_all_record_drafts_ask_in_selected_language_and_reject_provider_values_without_writes(self):
        from app.core import config

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        data_dir = Path(temporary.name)
        storage = StorageService(data_dir)
        with patch.object(config, "DATA_DIR", data_dir):
            drafts = [
                ("study.practice.draft", {"messages": ["I studied."], "language": "en", "evidence_claims": []}, "What date"),
                ("study.learning_evidence.draft", {"messages": ["Çalıştım."], "language": "tr", "evidence_claims": []}, "Hangi etkinliği"),
                ("study.question.draft", {"messages": ["Soru"], "language": "tr", "expected_question_field": "question_text", "state_token": None, "evidence_claims": []}, "Sorunun tam metnini"),
                ("study.exam.draft", {"messages": ["today"], "language": "en", "expected_exam_field": "date", "state_token": None, "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1, "evidence_claims": []}, "What date"),
                ("study.sectioned_exam.draft", {"messages": ["today"], "language": "tr", "expected_exam_field": "exam_type", "state_token": None, "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1, "evidence_claims": []}, "sınav türü"),
            ]
            for command, body, localized_prefix in drafts:
                result = run_json_line(json.dumps({"command": command, **body}, ensure_ascii=False))
                self.assertIn(result["status"], {"incomplete", "ambiguous"}, (command, result))
                self.assertFalse(result["write_allowed"])
                self.assertTrue(result["questions"], (command, result))
                self.assertTrue(result["questions"][0].startswith(localized_prefix), (command, result["questions"]))

                bad_body = dict(body)
                bad_body["evidence_claims"] = [{"field": "date", "quote": "2026-11-16", "value": "2026-11-16"}]
                rejected = run_json_line(json.dumps({"command": command, **bad_body}, ensure_ascii=False))
                self.assertEqual(rejected["status"], "error", (command, rejected))
                self.assertFalse(rejected["write_allowed"])

            self.assertEqual(storage.load_list("practice_sessions.json", PracticeSession), [])
            self.assertEqual(storage.load_list("learning_evidence.json", LearningEvidence), [])
            self.assertEqual(storage.load_list("questions.json", Question), [])
            self.assertEqual(storage.load_list("exams.json", Exam), [])


if __name__ == "__main__":
    unittest.main()
