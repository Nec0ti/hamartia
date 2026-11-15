import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import practice, study_agent
from app.models.schemas import PracticeSession, Settings
from app.services.storage import StorageService
from app.services.study_agent_practice import extract_fields, parse_proposal


FULL_MESSAGES = [
    "date: 2026-11-15\nsubject: Mathematics\ntopic: Functions",
    "correct: 7 incorrect: 2 blank: 1 duration_minutes: 18 duration_seconds: 0",
]
FULL_PROPOSAL = {
    "date": "2026-11-15", "subject": "Mathematics", "topic": "Functions",
    "correct": 7, "incorrect": 2, "blank": 1, "duration_minutes": 18, "duration_seconds": 0,
}


class StudyAgentPracticeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.storage = StorageService(self.data_dir)
        app = FastAPI()
        app.include_router(practice.router)
        self.data_patch = patch.object(practice, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.temp.cleanup()

    def draft(self, messages=FULL_MESSAGES, proposal=FULL_PROPOSAL, language="en"):
        return self.client.post("/practice/agent-draft", json={
            "messages": messages, "language": language, "proposal": proposal,
        })

    def create_body(self, draft, duplicate_choice=None):
        body = {
            "messages": FULL_MESSAGES, "language": "en", "proposal": FULL_PROPOSAL,
            "fields": dict(draft["fields"]), "evidence": dict(draft["evidence"]),
            "preview_digest": draft["preview_digest"],
        }
        if duplicate_choice is not None:
            body["duplicate_choice"] = duplicate_choice
        return body

    def sessions(self):
        return self.storage.load_list("practice_sessions.json", PracticeSession)

    def test_incomplete_data_asks_in_turkish_and_never_writes(self):
        response = self.draft(
            ["ders: Matematik", "konu: Fonksiyon"],
            {"subject": "Matematik", "topic": "Fonksiyon"},
            "tr",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("date", body["missing"])
        self.assertTrue(any("Lütfen" in question for question in body["questions"]))
        self.assertIsNone(body["preview_digest"])
        self.assertEqual(self.sessions(), [])

    def test_provider_cannot_add_unknown_field_or_invent_a_value(self):
        response = self.draft(proposal={**FULL_PROPOSAL, "settings": "changed"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.sessions(), [])

    def test_quote_tool_draft_resolves_host_transcript_and_create_rechecks_exact_preview(self):
        messages = [
            "I completed a practice test on Functions in Mathematics on 2026-11-15. "
            "I got 12 right, 3 wrong, left 1 blank; it took 45 minutes and 0 seconds."
        ]
        evidence_claims = [
            {"field": "subject", "quote": "in Mathematics"},
            {"field": "topic", "quote": "on Functions"},
            {"field": "date", "quote": "on 2026-11-15"},
            {"field": "correct", "quote": "12 right"},
            {"field": "incorrect", "quote": "3 wrong"},
            {"field": "blank", "quote": "left 1 blank"},
            {"field": "duration_minutes", "quote": "it took 45 minutes"},
            {"field": "duration_seconds", "quote": "0 seconds"},
        ]
        response = self.client.post("/practice/agent-draft", json={
            "messages": messages, "language": "en", "evidence_claims": evidence_claims,
        })
        self.assertEqual(response.status_code, 200)
        draft = response.json()
        self.assertEqual(draft["status"], "ready")
        self.assertEqual(draft["fields"]["correct"], 12)
        self.assertFalse(draft["proposal_mismatch"])
        self.assertEqual(self.sessions(), [])

        body = {
            "messages": messages, "language": "en", "evidence_claims": draft["evidence_claims"],
            "proposal": draft["proposal"], "fields": draft["fields"], "evidence": draft["evidence"],
            "preview_digest": draft["preview_digest"],
        }
        tampered = {**body, "fields": {**body["fields"], "correct": 13}}
        rejected = self.client.post("/practice/agent-create", json=tampered)
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(self.sessions(), [])

        saved = self.client.post("/practice/agent-create", json=body)
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(len(self.sessions()), 1)
        self.assertEqual(self.sessions()[0].correct, 12)

    def test_quote_tool_cannot_hide_cross_turn_conflict_and_prepare_never_writes(self):
        response = self.client.post("/practice/agent-draft", json={
            "messages": ["I got 5 right.", "or 7 right"], "language": "en",
            "evidence_claims": [{"field": "correct", "quote": "I got 5 right"}],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ambiguous")
        self.assertIn("correct", body["ambiguous"])
        self.assertIsNone(body["preview_digest"])
        self.assertEqual(self.sessions(), [])
        response = self.draft(proposal={**FULL_PROPOSAL, "correct": 70})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["proposal_mismatch"])
        self.assertEqual(response.json()["fields"]["correct"], 7)
        self.assertEqual(self.sessions(), [])

    def test_conflicting_values_are_reported_and_require_student_correction(self):
        response = self.draft(
            ["correct: 7 correct: 8"],
            {"correct": 7},
        )
        response = self.draft(["correct: 7 correct: 8"], {"correct": 7})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["proposal_mismatch"])
        self.assertTrue(response.json()["ambiguous"]["correct"])
        self.assertTrue(any("conflicting values" in question for question in response.json()["questions"]))
        self.assertEqual(self.sessions(), [])

        corrected = self.draft(
            ["correct: 7", "correct: 8", "correction: correct: 8"],
            {"correct": 8},
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertNotIn("correct", corrected.json()["ambiguous"])
        self.assertEqual(corrected.json()["fields"]["correct"], 8)

    def test_conflicting_values_across_turns_remain_ambiguous_until_explicit_correction(self):
        response = self.draft(["correct: 7", "correct: 8"], {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ambiguous"]["correct"], ["correct: 7", "correct: 8"])
        self.assertTrue(any("correction: correct: value" in item for item in response.json()["questions"]))
        self.assertFalse((self.data_dir / "practice_sessions.json").exists())

    def test_invalid_date_and_duration_are_localized_correction_questions(self):
        invalid_messages = [
            "date: 2026-02-31\nsubject: Mathematics\ntopic: Functions",
            "correct: 1 incorrect: 0 blank: 0 duration_minutes: 1 duration_seconds: 99",
        ]
        proposal = {
            "date": "2026-02-31", "subject": "Mathematics", "topic": "Functions",
            "correct": 1, "incorrect": 0, "blank": 0, "duration_minutes": 1, "duration_seconds": 99,
        }
        response = self.draft(invalid_messages, proposal, "tr")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["preview_digest"])
        self.assertTrue(any("geçersiz" in item for item in response.json()["questions"]))
        self.assertFalse((self.data_dir / "practice_sessions.json").exists())

    def test_preview_requires_exact_values_evidence_and_digest_before_any_write(self):
        draft = self.draft().json()
        body = self.create_body(draft)
        body["fields"]["correct"] = 8
        self.assertEqual(self.client.post("/practice/agent-create", json=body).status_code, 422)
        body = self.create_body(draft)
        body["preview_digest"] = "0" * 64
        self.assertEqual(self.client.post("/practice/agent-create", json=body).status_code, 409)
        body = self.create_body(draft)
        body["fields"]["settings"] = "restore"
        self.assertEqual(self.client.post("/practice/agent-create", json=body).status_code, 422)
        self.assertEqual(self.sessions(), [])

    def test_save_is_create_only_and_duplicate_choice_is_explicit_and_atomic(self):
        draft = self.draft().json()
        first = self.client.post("/practice/agent-create", json=self.create_body(draft))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(len(self.sessions()), 1)
        duplicate = self.draft().json()
        self.assertEqual(len(duplicate["conflicts"]), 1)
        rejected = self.client.post("/practice/agent-create", json=self.create_body(duplicate))
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(len(self.sessions()), 1)
        cancelled = self.client.post("/practice/agent-create", json=self.create_body(duplicate, "cancel"))
        self.assertEqual(cancelled.status_code, 409)
        self.assertEqual(len(self.sessions()), 1)
        explicit_new = self.client.post("/practice/agent-create", json=self.create_body(duplicate, "new"))
        self.assertEqual(explicit_new.status_code, 201)
        self.assertEqual(len(self.sessions()), 2)

    def test_concurrent_same_preview_saves_create_only_once_without_duplicate_approval(self):
        draft = self.draft().json()
        body = self.create_body(draft)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post("/practice/agent-create", json=body), range(2)))
        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        self.assertEqual(len(self.sessions()), 1)

    def test_closed_provider_json_parser_rejects_tools_and_non_integer_counts(self):
        self.assertEqual(parse_proposal('{"fields":{"correct":7}}'), {"correct": 7})
        for raw in (
            '{"fields":{"correct":"seven"}}',
            '{"fields":{"correct":7},"tool":"write"}',
            '{"fields":{"backup":"restore"}}',
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_proposal(raw)

    def test_comma_separated_student_values_keep_field_boundaries_and_quotes(self):
        message = "date: 2026-11-15, subject: Mathematics, topic: Functions, correct: 7, incorrect: 2, blank: 1, duration_minutes: 18, duration_seconds: 0"
        response = self.draft([message], FULL_PROPOSAL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fields"]["subject"], "Mathematics")
        self.assertEqual(response.json()["fields"]["topic"], "Functions")
        self.assertEqual(response.json()["evidence"]["topic"]["quote"], "topic: Functions")
        self.assertEqual(response.json()["fields"], FULL_PROPOSAL)
        self.assertEqual(response.json()["missing"], [])
        self.assertEqual(response.json()["ambiguous"], {})

    def test_labeled_numeric_prefixes_are_rejected_but_labeled_comma_boundaries_are_allowed(self):
        evidence, ambiguous = extract_fields([
            "correct: 1,200, incorrect: 2.5, blank: 3, duration_minutes: 1,000, duration_seconds: 30",
            "correct: 1 , 200",
            "correct: 1 . 5",
        ])
        self.assertEqual(ambiguous, {})
        self.assertNotIn("correct", evidence)
        self.assertNotIn("incorrect", evidence)
        self.assertNotIn("duration_minutes", evidence)
        self.assertEqual(evidence["blank"].value, 3)
        self.assertEqual(evidence["duration_seconds"].value, 30)


class ConfiguredStudyAgentProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        StorageService(self.data_dir).save_doc("settings.json", Settings(
            litellm_base_url="http://localhost:4000/v1", model_name="mock-model", api_key="mock-key",
        ))
        app = FastAPI()
        app.include_router(practice.router)
        app.include_router(study_agent.router)
        self.data_patch = patch.object(study_agent, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.practice_data_patch = patch.object(practice, "DATA_DIR", self.data_dir)
        self.practice_data_patch.start()
        self.client = TestClient(app)
        self.ai_patch = patch.object(study_agent, "AIService")
        self.ai_class = self.ai_patch.start()
        self.ai = self.ai_class.return_value
        self.ai.base_url = "http://localhost:4000/v1"
        self.ai.study_practice_proposal = AsyncMock(return_value='{"fields":{"subject":"Mathematics"}}')

    def tearDown(self):
        self.ai_patch.stop()
        self.client.close()
        self.data_patch.stop()
        self.practice_data_patch.stop()
        self.temp.cleanup()

    def payload(self):
        return {
            "consent": True, "message": "subject: Mathematics", "context": "",
            "language": "tr", "endpoint": "http://localhost:4000/v1", "model_name": "mock-model",
            "has_api_key": True, "workflow": "practice-entry", "messages": ["subject: Mathematics"],
        }

    def test_configured_provider_returns_mocked_proposal_and_receives_saved_language_code(self):
        response = self.client.post("/study-agent/local", json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"proposal": {"subject": "Mathematics"}})
        self.ai.study_practice_proposal.assert_awaited_once_with(["subject: Mathematics"], "tr")

    def test_configured_provider_proposal_is_untrusted_and_cannot_write(self):
        self.ai.study_practice_proposal.return_value = '{"fields":{"subject":"Physics"}}'
        response = self.client.post("/study-agent/local", json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"proposal": {"subject": "Physics"}})
        self.assertEqual(StorageService(self.data_dir).load_list("practice_sessions.json", PracticeSession), [])

    def test_configured_provider_overguess_is_replaced_by_localized_missing_question(self):
        self.ai.study_practice_proposal.return_value = '{"fields":{"subject":"Mathematics","topic":"Guessed topic"}}'
        provider_response = self.client.post("/study-agent/local", json={
            **self.payload(), "message": "ders: Matematik", "language": "tr", "messages": ["ders: Matematik"],
        })
        draft_response = self.client.post("/practice/agent-draft", json={
            "messages": ["ders: Matematik"], "language": "tr", "proposal": provider_response.json()["proposal"],
        })
        self.assertEqual(draft_response.status_code, 200)
        draft = draft_response.json()
        self.assertTrue(draft["proposal_mismatch"])
        self.assertEqual(draft["fields"]["subject"], "Matematik")
        self.assertNotIn("topic", draft["fields"])
        self.assertIn("topic", draft["missing"])
        self.assertIn("Lütfen konu bilgisini `topic: değer` biçiminde belirt.", draft["questions"])
        self.assertEqual(StorageService(self.data_dir).load_list("practice_sessions.json", PracticeSession), [])


if __name__ == "__main__":
    unittest.main()
