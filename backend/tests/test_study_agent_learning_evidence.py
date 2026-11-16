import tempfile
import unittest
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.api import learning_evidence, study_agent
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import LearningEvidence, Settings
from app.services.study_agent_learning_evidence import dispatch_provider_tool, prepare_learning_evidence
from app.services.storage import StorageService


MESSAGES = [
    "I completed reading chapter 2 and made notes.",
    "Biology",
    "Cell division",
    "2026-11-16",
    "I observed that comparing diagrams made the stages easier to distinguish.",
]
CLAIMS = [
    {"field": "activity", "quote": MESSAGES[0]},
    {"field": "subject", "quote": MESSAGES[1]},
    {"field": "topic", "quote": MESSAGES[2]},
    {"field": "date", "quote": "2026-11-16"},
    {"field": "observation", "quote": MESSAGES[4]},
]


class StudyAgentLearningEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.storage = StorageService(self.data_dir)
        app = FastAPI()
        app.add_exception_handler(__import__("fastapi").exceptions.RequestValidationError, safe_validation_error_handler)
        app.include_router(learning_evidence.router)
        self.data_patch = patch.object(learning_evidence, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.temp.cleanup()

    def draft_body(self, messages=MESSAGES, claims=CLAIMS, language="en"):
        return {"messages": messages, "language": language, "evidence_claims": claims}

    def draft(self, messages=MESSAGES, claims=CLAIMS, language="en"):
        response = self.client.post("/learning-evidence/agent-draft", json=self.draft_body(messages, claims, language))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def create_body(self, draft, messages=MESSAGES, claims=CLAIMS, approval_id=None, language="en"):
        return {
            "messages": messages,
            "language": language,
            "evidence_claims": claims,
            "fields": draft["fields"],
            "evidence": draft["verified_evidence"],
            "preview_digest": draft["preview_digest"],
            "approval_id": approval_id or str(uuid.uuid4()),
        }

    def rows(self):
        return self.storage.load_list("learning_evidence.json", LearningEvidence)

    def test_tool_contract_is_quote_only_and_host_resolves_exact_fields(self):
        prepared = dispatch_provider_tool({"evidence": CLAIMS}, messages=MESSAGES, language="en")
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(prepared["fields"], {
            "date": "2026-11-16",
            "subject": "Biology",
            "topic": "Cell division",
            "activity": MESSAGES[0],
            "observation": MESSAGES[4],
            "reference_url": "",
        })
        self.assertEqual(prepared["verified_evidence"]["activity"]["quote"], MESSAGES[0])
        self.assertEqual(prepared["verified_evidence"]["observation"]["start"], 0)
        self.assertFalse(prepared["write_allowed"])
        with self.assertRaises(ValueError):
            dispatch_provider_tool({"evidence": [{"field": "subject", "quote": "Biology", "value": "Chemistry"}]}, messages=MESSAGES, language="en")
        with self.assertRaises(ValueError):
            dispatch_provider_tool({"evidence": [{"field": "record_id", "quote": "x"}]}, messages=MESSAGES, language="en")

    def test_follow_up_state_is_host_ordered_and_does_not_skip_missing_fields(self):
        body = self.draft_body(["Biology"], [{"field": "subject", "quote": "Biology"}], "tr")
        response = self.client.post("/learning-evidence/agent-draft", json=body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("activity", result["missing"])
        self.assertEqual(result["fields"], {})
        self.assertIn("Hangi etkinliği", result["questions"][0])
        self.assertIsNone(result["preview_digest"])
        self.assertEqual(self.rows(), [])

    def test_negated_hypothetical_uncertain_and_noncompletion_activity_are_no_write(self):
        for activity in (
            "I might read chapter 2 tomorrow.",
            "I completed nothing today.",
            "If I had time, I completed a chapter.",
            "I did not complete chapter 2.",
            "I read chapter 2.",
            "Maybe I completed the chapter?",
            "Yarın bölümü çalışacağım.",
            "Bölümü henüz tamamlamadım.",
            "Belki bölümü çalıştım.",
        ):
            with self.subTest(activity=activity):
                messages = [activity, *MESSAGES[1:]]
                claims = [{**CLAIMS[0], "quote": activity}, *CLAIMS[1:]]
                result = prepare_learning_evidence(messages, "en", claims)
                self.assertEqual(result["status"], "ambiguous")
                self.assertIsNone(result["preview_digest"])
                self.assertIn("activity", result["ambiguous"])
                response = self.client.post("/learning-evidence/agent-create", json={
                    "messages": messages, "language": "en", "evidence_claims": claims,
                    "fields": {"date": "2026-11-16", "subject": "Biology", "topic": "Cell division", "activity": activity, "observation": MESSAGES[4], "reference_url": ""},
                    "evidence": {}, "preview_digest": "0" * 64, "approval_id": str(uuid.uuid4()),
                })
                self.assertNotEqual(response.status_code, 201)
                self.assertEqual(self.rows(), [])

    def test_turkish_explicit_past_activity_is_accepted(self):
        messages = ["Bugün sekiz soru çözdüm.", "Biyoloji", "Hücre bölünmesi", "2026-11-16", "Şemaları karşılaştırınca aşamaları ayırt etmek kolaylaştı."]
        claims = [
            {"field": "activity", "quote": messages[0]},
            {"field": "subject", "quote": messages[1]},
            {"field": "topic", "quote": messages[2]},
            {"field": "date", "quote": messages[3]},
            {"field": "observation", "quote": messages[4]},
        ]
        result = prepare_learning_evidence(messages, "tr", claims)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fields"]["activity"], messages[0])
        self.assertEqual(result["language"], "tr")

    def test_activity_is_preserved_as_qualified_self_report_without_completion_inference(self):
        for activity in (
            "I completed chapter 2 except the final section.",
            "I worked on chapter 2.",
            "Son bölüm hariç 2. bölümü tamamladım.",
        ):
            with self.subTest(activity=activity):
                messages = [activity, *MESSAGES[1:]]
                claims = [{**CLAIMS[0], "quote": activity}, *CLAIMS[1:]]
                result = prepare_learning_evidence(messages, "en" if activity.startswith("I ") else "tr", claims)
                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["fields"]["activity"], activity)
                self.assertEqual(result["verified_evidence"]["activity"]["quote"], activity)

    def test_quote_must_be_unique_and_match_expected_turn(self):
        duplicated = [*MESSAGES, "Biology"]
        result = prepare_learning_evidence(duplicated, "en", CLAIMS)
        self.assertNotEqual(result["status"], "ready")
        wrong_turn = ["Biology", *MESSAGES[1:]]
        result = prepare_learning_evidence(wrong_turn, "en", [{**CLAIMS[0], "quote": "Biology"}, *CLAIMS[1:]])
        self.assertNotEqual(result["status"], "ready")
        self.assertIsNone(result["preview_digest"])

    def test_date_url_and_schema_bounds_are_explicit_and_url_is_never_fetched(self):
        for date in ("today", "15/11/2026", "2026-02-30"):
            with self.subTest(date=date):
                messages = [*MESSAGES]
                messages[3] = date
                claims = [*CLAIMS]
                claims[3] = {"field": "date", "quote": date}
                result = prepare_learning_evidence(messages, "en", claims)
                self.assertNotEqual(result["status"], "ready")
                self.assertIsNone(result["preview_digest"])
        messages = [*MESSAGES]
        messages[4] += " https://example.org/notes"
        claims = [*CLAIMS, {"field": "reference_url", "quote": "https://example.org/notes"}]
        result = prepare_learning_evidence(messages, "en", claims)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fields"]["reference_url"], "https://example.org/notes")
        self.assertFalse(result["rejected_claims"])
        punctuated_url = "https://example.org/notes."
        punctuated_messages = [*MESSAGES]
        punctuated_messages[4] += " " + punctuated_url
        punctuated_claims = [*CLAIMS, {"field": "reference_url", "quote": punctuated_url}]
        result = prepare_learning_evidence(punctuated_messages, "en", punctuated_claims)
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["preview_digest"])
        self.assertIn("reference_url", result["ambiguous"])
        injected = [*CLAIMS, {"field": "reference_url", "quote": "https://attacker.example"}]
        result = prepare_learning_evidence(MESSAGES, "en", injected)
        self.assertEqual(result["fields"]["reference_url"], "")
        self.assertTrue(result["rejected_claims"])

        malformed_url_messages = [*MESSAGES]
        malformed_url_messages[4] += " https://bad!.example/path"
        malformed_url_claims = [*CLAIMS, {"field": "reference_url", "quote": "https://bad!.example/path"}]
        result = prepare_learning_evidence(malformed_url_messages, "en", malformed_url_claims)
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["preview_digest"])
        self.assertIn("reference_url", result["ambiguous"])

        duplicate_url_claims = [*CLAIMS,
            {"field": "reference_url", "quote": "https://example.org/notes"},
            {"field": "reference_url", "quote": "https://example.org/notes"},
        ]
        url_messages = [*MESSAGES]
        url_messages[4] += " https://example.org/notes"
        result = prepare_learning_evidence(url_messages, "en", duplicate_url_claims)
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["preview_digest"])

    def test_preview_requires_exact_explicit_approval_and_recomputes(self):
        draft = self.draft()
        self.assertEqual(self.rows(), [])
        body = self.create_body(draft)
        created = self.client.post("/learning-evidence/agent-create", json=body)
        self.assertEqual(created.status_code, 201, created.text)
        replay = self.client.post("/learning-evidence/agent-create", json=body)
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()["id"], created.json()["id"])
        self.assertEqual(len(self.rows()), 1)

        changed_messages = [*MESSAGES]
        changed_messages[4] = "I noticed that drawing the stages helped me remember them."
        changed_claims = [*CLAIMS]
        changed_claims[4] = {"field": "observation", "quote": changed_messages[4]}
        changed_draft = self.draft(changed_messages, changed_claims)
        changed = self.create_body(changed_draft, changed_messages, changed_claims, body["approval_id"])
        response = self.client.post("/learning-evidence/agent-create", json=changed)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.rows()), 1)

        stale = dict(body)
        stale["fields"] = {**stale["fields"], "observation": "a changed approved value"}
        response = self.client.post("/learning-evidence/agent-create", json=stale)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.rows()), 1)

    def test_same_approval_concurrently_creates_one_row_and_replays_same_id(self):
        draft = self.draft()
        body = self.create_body(draft)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: self.client.post("/learning-evidence/agent-create", json=body), range(8)))
        self.assertTrue(all(response.status_code == 201 for response in responses), [response.text for response in responses])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(len({response.json()["id"] for response in responses}), 1)

    def test_approval_tombstone_prevents_recreation_after_user_deletes_record(self):
        draft = self.draft()
        body = self.create_body(draft)
        created = self.client.post("/learning-evidence/agent-create", json=body)
        self.assertEqual(created.status_code, 201, created.text)
        record_id = created.json()["id"]
        deleted = self.client.delete(f"/learning-evidence/{record_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.rows(), [])

        replay = self.client.post("/learning-evidence/agent-create", json=body)
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(self.rows(), [])
        ledger_path = self.data_dir / learning_evidence.AGENT_APPROVALS_FILE
        ledger_text = ledger_path.read_text(encoding="utf-8")
        self.assertNotIn("Biology", ledger_text)
        self.assertNotIn(MESSAGES[-1], ledger_text)
        ledger = json.loads(ledger_text)
        self.assertEqual(set(ledger), {"approval_ids"})
        self.assertEqual(ledger["approval_ids"], [body["approval_id"]])

    def test_configured_provider_entrypoint_uses_mock_tool_hints_and_never_writes(self):
        self.storage.save_doc("settings.json", Settings(
            litellm_base_url="https://provider.example/v1", model_name="mock-model", api_key="",
        ))
        app = FastAPI()
        app.add_exception_handler(__import__("fastapi").exceptions.RequestValidationError, safe_validation_error_handler)
        app.include_router(study_agent.router)
        with patch.object(study_agent, "DATA_DIR", self.data_dir), \
             patch.object(learning_evidence, "DATA_DIR", self.data_dir), \
             patch.object(study_agent, "AIService") as service:
            fake = service.return_value
            fake.base_url = "https://provider.example/v1"
            fake.study_learning_evidence_prepare = AsyncMock(return_value={"evidence_claims": CLAIMS})
            with TestClient(app) as client:
                response = client.post("/study-agent/local", json={
                    "consent": True,
                    "message": MESSAGES[-1],
                    "context": "",
                    "language": "en",
                    "endpoint": "https://provider.example/v1",
                    "model_name": "mock-model",
                    "has_api_key": False,
                    "workflow": "learning-evidence-entry",
                    "expected_evidence_field": "activity",
                    "messages": MESSAGES,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "ready")
                self.assertEqual(self.rows(), [])

                fake.study_learning_evidence_prepare = AsyncMock(return_value={
                    "evidence_claims": [{"field": "subject", "quote": "Biology"}],
                })
                invalid = client.post("/study-agent/local", json={
                    "consent": True,
                    "message": MESSAGES[-1],
                    "context": "",
                    "language": "en",
                    "endpoint": "https://provider.example/v1",
                    "model_name": "mock-model",
                    "has_api_key": False,
                    "workflow": "learning-evidence-entry",
                    "expected_evidence_field": "activity",
                    "messages": ["Biology"],
                })
                self.assertEqual(invalid.status_code, 200)
                self.assertEqual(invalid.json()["status"], "incomplete")
                self.assertEqual(self.rows(), [])
            self.assertEqual(fake.study_learning_evidence_prepare.await_count, 1)


if __name__ == "__main__":
    unittest.main()
