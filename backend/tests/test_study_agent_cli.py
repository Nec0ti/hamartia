import json
import subprocess
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.hamartia_cli import MAX_LINE_LENGTH, run_json_line
from app.services.study_agent_cli import EvidenceQuote, ProviderToolArguments, dispatch_cli, dispatch_provider_tool, parse_quote_value, prepare_practice
from app.services.study_agent_practice import extract_fields

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
        self.assertEqual(len(result["preview_digest"]), 64)

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
        for later in ("Maybe 7 right.", "Perhaps 7 right.", "Alternatively 7 right."):
            with self.subTest(later=later):
                result = prepare_practice(["I got 5 right.", later], "en", [{"field": "correct", "quote": "5 right"}])
                self.assertIn("correct", result["ambiguous"])
        for later, language in (("or the next day", "en"), ("ya da ertesi gün", "tr")):
            with self.subTest(later=later):
                result = prepare_practice(
                    ["I studied on 2026-11-15." if language == "en" else "Tarih 2026-11-15.", later], language,
                    [{"field": "date", "quote": "on 2026-11-15" if language == "en" else "Tarih 2026-11-15"}],
                )
                self.assertIn("date", result["ambiguous"])
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

    def test_cli_jsonl_dispatch_has_only_read_only_prepare_command(self):
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
            cwd=BACKEND_DIR, check=True, timeout=5,
        )
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["write_allowed"])

    def test_cli_process_bounds_and_drains_oversized_lines(self):
        request = {"command": "study.practice.prepare", "language": "en", "messages": MESSAGES, "evidence": CLAIMS}
        process = subprocess.run(
            [sys.executable, "-m", "app.hamartia_cli", "--jsonl"],
            input='{"padding":"' + ("x" * MAX_LINE_LENGTH) + '"}\n' + json.dumps(request) + "\n",
            text=True, capture_output=True, cwd=BACKEND_DIR, check=True, timeout=5,
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


if __name__ == "__main__":
    unittest.main()
