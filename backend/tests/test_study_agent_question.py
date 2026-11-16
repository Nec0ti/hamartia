import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import questions, study_agent
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Question, QuestionDeletedApprovalLedger, Settings
from app.services.storage import StorageService
from app.services.study_agent_question import (
    QUESTION_STATE_MAX_AGE_SECONDS,
    QuestionToolArguments,
    issue_question_state_token,
    prepare_question_capture,
    provider_tool_parameters,
    resolve_question_state_token,
)

QUESTION_TEXT = "If a rectangle has width 4 cm and length 7 cm, what is its area?"


class StudyAgentQuestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.storage = StorageService(self.data_dir)
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(questions.router)
        self.data_patch = patch.object(questions, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.upload_patch = patch.object(questions, "UPLOAD_DIR", self.data_dir / "uploads")
        self.upload_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.upload_patch.stop()
        self.data_patch.stop()
        self.temp.cleanup()

    def rows(self):
        return self.storage.load_list("questions.json", Question)

    def claim(self, field, quote):
        return {"field": field, "quote": quote}

    def complete_draft(self, text=QUESTION_TEXT, subject="Biology", topic="Geometry"):
        messages = [text, subject, topic]
        claims = [self.claim("question_text", text), self.claim("subject", subject), self.claim("topic", topic)]
        result = prepare_question_capture(messages, "en", claims)
        self.assertEqual(result["status"], "ready")
        return messages, claims, result

    def create_body(self, draft, messages, claims, approval_id=None):
        return {
            "messages": messages,
            "language": draft["language"],
            "evidence_claims": claims,
            "fields": draft["fields"],
            "evidence": draft["verified_evidence"],
            "preview_digest": draft["preview_digest"],
            "approval_id": approval_id or str(uuid.uuid4()),
        }

    def draft_request(self, messages, field, claims, state_token=None, language="en"):
        return self.client.post("/questions/agent-draft", json={
            "messages": messages,
            "language": language,
            "expected_question_field": field,
            "state_token": state_token,
            "evidence_claims": claims,
        })

    def test_tool_contract_accepts_only_one_field_and_exact_quote(self):
        schema = provider_tool_parameters()
        self.assertEqual(schema["required"], ["evidence"])
        self.assertIs(schema["additionalProperties"], False)
        item_schema = schema["properties"]["evidence"]["items"]
        self.assertEqual(item_schema["required"], ["field", "quote"])
        self.assertEqual(set(item_schema["properties"]), {"field", "quote"})
        self.assertEqual(item_schema["properties"]["field"]["enum"], ["question_text", "subject", "topic"])
        with self.assertRaises(ValueError):
            QuestionToolArguments.model_validate({"evidence": [{"field": "subject", "quote": "Biology", "value": "Biology"}]})
        with self.assertRaises(ValueError):
            QuestionToolArguments.model_validate({"evidence": [{"field": "question_text", "quote": QUESTION_TEXT}, {"field": "subject", "quote": "Biology"}]})

    def test_host_parser_requires_exact_sequential_turns_and_localized_skip(self):
        first = prepare_question_capture([QUESTION_TEXT], "en", [self.claim("question_text", QUESTION_TEXT)])
        self.assertEqual(first["status"], "incomplete")
        self.assertEqual(first["expected_field"], "subject")
        self.assertIn("type “skip”", first["questions"][0])
        second = prepare_question_capture([QUESTION_TEXT, "atla"], "tr", [
            self.claim("question_text", QUESTION_TEXT), self.claim("subject", "atla"),
        ])
        self.assertEqual(second["status"], "incomplete")
        self.assertIn("konu", second["questions"][0].lower())
        ready = prepare_question_capture([QUESTION_TEXT, "atla", "Geometry"], "tr", [
            self.claim("question_text", QUESTION_TEXT), self.claim("subject", "atla"), self.claim("topic", "Geometry"),
        ])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["fields"], {"question_text": QUESTION_TEXT, "subject": "", "topic": "Geometry"})
        self.assertIsNone(ready["fields"].get("analysis"))
        self.assertEqual(ready["verified_evidence"]["question_text"]["quote"], QUESTION_TEXT)
        self.assertEqual(ready["verified_evidence"]["subject"]["skipped"], True)

        repeated_skip = prepare_question_capture([QUESTION_TEXT, "atla", "atla"], "tr", [
            self.claim("question_text", QUESTION_TEXT), self.claim("subject", "atla"),
            self.claim("topic", "atla"),
        ])
        self.assertEqual(repeated_skip["status"], "ready")
        self.assertEqual(repeated_skip["fields"], {"question_text": QUESTION_TEXT, "subject": "", "topic": ""})
        self.assertTrue(repeated_skip["verified_evidence"]["subject"]["skipped"])
        self.assertTrue(repeated_skip["verified_evidence"]["topic"]["skipped"])

    def test_noncontent_hypothetical_future_and_uncertain_turns_do_not_preview(self):
        for text in (
            "Maybe I will save this question later.",
            "I plan to paste the question tomorrow.",
            "If I had the question, I would add it.",
            "Do not save this yet.",
            "Belki daha sonra ekleyeceğim.",
            "Kaydetme, bu soru değil.",
        ):
            with self.subTest(text=text):
                result = prepare_question_capture([text], "en", [self.claim("question_text", text)])
                self.assertEqual(result["status"], "ambiguous")
                self.assertIsNone(result["preview_digest"])
                self.assertEqual(result["fields"], {})

    def test_partial_or_repeated_quote_and_out_of_order_hint_fail_closed(self):
        partial = prepare_question_capture([QUESTION_TEXT], "en", [self.claim("question_text", "rectangle has width 4 cm")])
        self.assertEqual(partial["status"], "ambiguous")
        repeated = prepare_question_capture(["x+1=2", "x+1=2"], "en", [self.claim("question_text", "x+1=2")])
        self.assertEqual(repeated["status"], "ambiguous")
        out_of_order = prepare_question_capture([QUESTION_TEXT, "Biology"], "en", [self.claim("subject", "Biology")])
        self.assertEqual(out_of_order["status"], "incomplete")
        self.assertEqual(out_of_order["fields"], {})

    def test_draft_state_is_host_derived_and_bound_to_one_appended_turn(self):
        first = self.draft_request([QUESTION_TEXT], "question_text", [self.claim("question_text", QUESTION_TEXT)])
        self.assertEqual(first.status_code, 200, first.text)
        first_draft = first.json()
        self.assertEqual(first_draft["expected_field"], "subject")
        self.assertFalse(first_draft["write_allowed"])

        second = self.draft_request([QUESTION_TEXT, "Biology"], "subject", [self.claim("subject", "Biology")], first_draft["state_token"])
        self.assertEqual(second.status_code, 200, second.text)
        second_draft = second.json()
        self.assertEqual(second_draft["expected_field"], "topic")

        wrong_turn = self.draft_request([QUESTION_TEXT, "Biology", "Geometry"], "topic", [self.claim("topic", "Biology")], second_draft["state_token"])
        self.assertEqual(wrong_turn.status_code, 422, wrong_turn.text)
        self.assertNotIn("preview_digest", wrong_turn.json())

        fresh_token = issue_question_state_token([QUESTION_TEXT, "Biology"], "en", {
            "question_text": {"quote": QUESTION_TEXT}, "subject": {"quote": "Biology"},
        })
        correct_turn = self.draft_request([QUESTION_TEXT, "Biology", "Geometry"], "topic", [self.claim("topic", "Geometry")], fresh_token)
        self.assertEqual(correct_turn.status_code, 200, correct_turn.text)
        self.assertEqual(correct_turn.json()["status"], "ready")
        self.assertEqual(correct_turn.json()["fields"]["topic"], "Geometry")
        self.assertEqual(self.rows(), [])

    def test_same_skip_response_can_fill_each_optional_field_in_its_expected_turn(self):
        first = self.draft_request([QUESTION_TEXT], "question_text", [self.claim("question_text", QUESTION_TEXT)], language="tr")
        self.assertEqual(first.status_code, 200, first.text)
        second = self.draft_request(
            [QUESTION_TEXT, "atla"], "subject", [self.claim("subject", "atla")],
            first.json()["state_token"], language="tr",
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["expected_field"], "topic")
        third = self.draft_request(
            [QUESTION_TEXT, "atla", "atla"], "topic", [self.claim("topic", "atla")],
            second.json()["state_token"], language="tr",
        )
        self.assertEqual(third.status_code, 200, third.text)
        self.assertEqual(third.json()["status"], "ready")
        self.assertEqual(third.json()["fields"], {"question_text": QUESTION_TEXT, "subject": "", "topic": ""})
        self.assertTrue(third.json()["verified_evidence"]["subject"]["skipped"])
        self.assertTrue(third.json()["verified_evidence"]["topic"]["skipped"])

    def test_empty_prior_state_cannot_advance_from_a_quote_in_an_older_turn(self):
        first_text = "A triangle has sides 3, 4, and 5. Find its perimeter."
        newest_text = "A rectangle has width 4 and length 7. Find its area."
        first = self.draft_request([first_text], "question_text", [])
        self.assertEqual(first.status_code, 200, first.text)
        token = first.json()["state_token"]

        stale = self.draft_request(
            [first_text, newest_text], "question_text", [self.claim("question_text", first_text)], token,
        )
        self.assertEqual(stale.status_code, 422, stale.text)
        self.assertNotIn("preview_digest", stale.json())
        self.assertEqual(self.rows(), [])

        fresh_token = issue_question_state_token([first_text], "en", {})
        current = self.draft_request(
            [first_text, newest_text], "question_text", [self.claim("question_text", newest_text)], fresh_token,
        )
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["expected_field"], "subject")
        self.assertEqual(current.json()["fields"]["question_text"], newest_text)
        self.assertEqual(self.rows(), [])

    def test_state_token_is_canonical_one_use_and_bound_to_exact_prefix(self):
        prefix = [QUESTION_TEXT]
        evidence = {"question_text": {"quote": QUESTION_TEXT}}
        next_turn = [QUESTION_TEXT, "Biology"]
        token = issue_question_state_token(prefix, "en", evidence)
        self.assertEqual(resolve_question_state_token(token, next_turn, "en"), [self.claim("question_text", QUESTION_TEXT)])
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            resolve_question_state_token(token, next_turn, "en")

        body, signature = token.split(".", 1)
        variants = [f"{body}.{signature}!!!", f"{body}.{signature}=", f"{body}=.{signature}"]
        for variant in variants:
            with self.subTest(variant=variant[-8:]), self.assertRaisesRegex(ValueError, "invalid or expired"):
                resolve_question_state_token(variant, next_turn, "en")

        wrong_prefix_token = issue_question_state_token(prefix, "en", evidence)
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            resolve_question_state_token(wrong_prefix_token, ["A different problem?", "Biology"], "en")
        wrong_count_token = issue_question_state_token(prefix, "en", evidence)
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            resolve_question_state_token(wrong_count_token, [*next_turn, "Geometry"], "en")
        expired_token = issue_question_state_token(prefix, "en", evidence)
        expiry = time.time() + QUESTION_STATE_MAX_AGE_SECONDS + 1
        with patch("app.services.study_agent_question.time.time", return_value=expiry):
            with self.assertRaisesRegex(ValueError, "invalid or expired"):
                resolve_question_state_token(expired_token, next_turn, "en")

    def test_create_recomputes_preview_approves_once_and_altered_replay_conflicts(self):
        messages, claims, draft = self.complete_draft()
        body = self.create_body(draft, messages, claims)
        first = self.client.post("/questions/agent-create", json=body)
        self.assertEqual(first.status_code, 201, first.text)
        record = first.json()
        self.assertEqual(record["ocr_text"], QUESTION_TEXT)
        self.assertEqual(record["subject"], "Biology")
        self.assertEqual(record["topic"], "Geometry")
        self.assertEqual(record["image_path"], "")
        self.assertEqual(record["image_name"], "")
        self.assertIsNone(record["analysis"])
        self.assertEqual(record["curriculum_reference"], {
            "framework": "", "source": "", "version": "", "grade_year": "", "unit_theme": "",
            "learning_outcome": "", "process_component": "", "source_url": "",
        })
        self.assertEqual(record["hamartia_tag"], "[Knowledge Gap]")
        replay = self.client.post("/questions/agent-create", json=body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], record["id"])
        self.assertEqual(len(self.rows()), 1)
        altered = {**body, "fields": {**body["fields"], "topic": "Algebra"}}
        conflict = self.client.post("/questions/agent-create", json=altered)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(len(self.rows()), 1)

    def test_invalid_or_tampered_preview_never_writes(self):
        messages, claims, draft = self.complete_draft()
        body = self.create_body(draft, messages, claims)
        body["fields"]["subject"] = "Chemistry"
        response = self.client.post("/questions/agent-create", json=body)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.rows(), [])
        incomplete = {**body, "fields": {"question_text": "Only text", "subject": "", "topic": ""}}
        incomplete["evidence_claims"] = [claims[0], claims[1], claims[2]]
        incomplete["fields"]["subject"] = "Chemistry"
        self.assertNotEqual(self.client.post("/questions/agent-create", json=incomplete).status_code, 201)
        self.assertEqual(self.rows(), [])

    def test_concurrent_exact_approval_creates_one_question(self):
        messages, claims, draft = self.complete_draft()
        body = self.create_body(draft, messages, claims)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: self.client.post("/questions/agent-create", json=body), range(8)))
        self.assertTrue(all(response.status_code == 201 for response in responses), [r.text for r in responses])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)

    def test_delete_keeps_content_free_tombstone_and_replay_cannot_recreate(self):
        messages, claims, draft = self.complete_draft()
        body = self.create_body(draft, messages, claims)
        created = self.client.post("/questions/agent-create", json=body)
        self.assertEqual(created.status_code, 201, created.text)
        deleted = self.client.delete(f"/questions/{created.json()['id']}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        ledger = self.storage.load_doc("question_agent_approvals.json", QuestionDeletedApprovalLedger)
        self.assertEqual([str(value) for value in ledger.approval_ids], [str(body["approval_id"])])
        self.assertEqual(self.rows(), [])
        replay = self.client.post("/questions/agent-create", json=body)
        self.assertEqual(replay.status_code, 409, replay.text)
        self.assertEqual(self.rows(), [])
        raw = (self.data_dir / "question_agent_approvals.json").read_text()
        self.assertNotIn(QUESTION_TEXT, raw)
        self.assertNotIn("Biology", raw)

    def test_composed_configured_provider_rejects_old_turn_quote_even_without_prior_claims(self):
        endpoint = "https://provider.example/v1"
        self.storage.save_doc("settings.json", Settings(
            litellm_base_url=endpoint, model_name="mock-model", api_key="",
        ))
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(study_agent.router)
        with patch.object(study_agent, "DATA_DIR", self.data_dir), patch.object(study_agent, "AIService") as service:
            fake = service.return_value
            fake.base_url = endpoint
            with TestClient(app) as client:
                first_text = "A triangle has sides 3, 4, and 5. Find its perimeter."
                first_messages = [first_text]
                fake.study_question_prepare = AsyncMock(return_value={"current_evidence_claims": []})
                first = client.post("/study-agent/local", json={
                    "consent": True, "message": first_text, "context": "", "language": "en",
                    "endpoint": endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": "question-entry", "expected_question_field": "question_text",
                    "messages": first_messages,
                })
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["status"], "incomplete")
                token = first.json()["state_token"]
                self.assertEqual(self.rows(), [])

                newest_text = "A rectangle has width 4 and length 7. Find its area."
                fake.study_question_prepare = AsyncMock(return_value={
                    "current_evidence_claims": [{"field": "question_text", "quote": first_text}],
                })
                stale = client.post("/study-agent/local", json={
                    "consent": True, "message": newest_text, "context": "", "language": "en",
                    "endpoint": endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": "question-entry", "expected_question_field": "question_text",
                    "question_state_token": token, "messages": [*first_messages, newest_text],
                })
                self.assertEqual(stale.status_code, 422, stale.text)
                self.assertIn("current host-expected student turn", stale.json()["detail"])
                fake.study_question_prepare.assert_awaited_once()
                self.assertEqual(self.rows(), [])

    def test_manual_multipart_question_creation_remains_available(self):
        response = self.client.post("/questions", data={"ocr_text": "manual text", "subject": "Math"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0].ocr_text, "manual text")
        self.assertEqual(self.rows()[0].id.startswith("q_agent_"), False)


if __name__ == "__main__":
    unittest.main()
