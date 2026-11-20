import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.api import study_agent
from app.core.http_errors import safe_validation_error_handler
from app.models.schemas import Settings, legacy_yks_profile
from app.services.continuation_tokens import reserve, finish, use
from app.services.study_agent_custom_exam import issue_state_token as issue_custom_token
from app.services.study_agent_exam import issue_exam_state_token
from app.services.study_agent_learning_evidence import issue_learning_evidence_state_token
from app.services.study_agent_question import issue_question_state_token
from app.services.study_agent_sectioned_exam import issue_state_token as issue_sectioned_token


class ContinuationTokenRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.endpoint = "https://provider.example/v1"
        from app.services.storage import StorageService
        StorageService(self.data_dir).save_doc("settings.json", Settings(
            litellm_base_url=self.endpoint, model_name="mock-model", api_key="",
        ))
        app = FastAPI()
        app.add_exception_handler(RequestValidationError, safe_validation_error_handler)
        app.include_router(study_agent.router)
        self.data_patch = patch.object(study_agent, "DATA_DIR", self.data_dir)
        self.data_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.data_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def workflows():
        profile = legacy_yks_profile()
        prefix = "I completed reading chapter two and made notes."
        question = "If a rectangle has width 4 cm and length 7 cm, what is its area?"
        return [
            ("exam-entry", "study_exam_prepare", "exam_state_token", "expected_exam_field", "subject",
             ["2026-11-16"], [{"field": "date", "quote": "2026-11-16", "message_index": 0}],
             issue_exam_state_token(["2026-11-16"], "en", [{"field": "date", "quote": "2026-11-16", "message_index": 0}], profile.profile_id, profile.version),
             [{"field": "subject", "quote": "Biology"}], "current_evidence_claims"),
            ("sectioned-exam-entry", "study_sectioned_exam_prepare", "sectioned_exam_state_token", "expected_sectioned_exam_field", "date",
             ["TYT"], [{"field": "exam_type", "quote": "TYT", "message_index": 0}],
             issue_sectioned_token(["TYT"], "en", [{"field": "exam_type", "quote": "TYT", "message_index": 0}], profile),
             [{"field": "date", "quote": "2026-11-16"}], "current_evidence_claims"),
            ("custom-sectioned-exam-entry", "study_custom_exam_prepare", "custom_exam_state_token", "expected_custom_exam_field", "date",
             ["Personal mock"], [{"field": "format_name", "quote": "Personal mock", "message_index": 0}],
             issue_custom_token(["Personal mock"], "en", [{"field": "format_name", "quote": "Personal mock", "message_index": 0}], profile),
             [{"field": "date", "quote": "2026-11-16"}], "current_evidence_claims"),
            ("question-entry", "study_question_prepare", "question_state_token", "expected_question_field", "subject",
             [question], [{"field": "question_text", "quote": question, "message_index": 0}],
             issue_question_state_token([question], "en", {"question_text": {"quote": question}}),
             [{"field": "subject", "quote": "Biology"}], "current_evidence_claims"),
            ("learning-evidence-entry", "study_learning_evidence_prepare", "state_token", "expected_evidence_field", "subject",
             [prefix], [{"field": "activity", "quote": prefix}],
             issue_learning_evidence_state_token([prefix], "en", {"activity": {"quote": prefix}}),
             [{"field": "subject", "quote": "Biology"}], "evidence_claims"),
        ]

    def test_every_workflow_releases_after_wrong_field_and_provider_error_then_commits_success(self):
        for workflow, method, token_key, field_key, expected, prefix, _, token, claims, response_key in self.workflows():
            with self.subTest(workflow=workflow), patch.object(study_agent, "AIService") as service:
                fake = service.return_value
                fake.base_url = self.endpoint
                setattr(fake, method, AsyncMock(side_effect=[RuntimeError("provider unavailable"), {response_key: claims}]))
                current = "Biology" if expected == "subject" else "2026-11-16"
                body = {
                    "consent": True, "message": current, "context": "", "language": "en",
                    "endpoint": self.endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": workflow, field_key: expected, token_key: token,
                    "messages": [*prefix, current],
                }
                if workflow in {"exam-entry", "sectioned-exam-entry", "custom-sectioned-exam-entry"}:
                    body.update(scoring_profile_id="legacy-yks", scoring_profile_version=1)

                wrong_field = {
                    "exam-entry": "date", "sectioned-exam-entry": "exam_type",
                    "custom-sectioned-exam-entry": "format_name", "question-entry": "topic",
                    "learning-evidence-entry": "topic",
                }[workflow]
                wrong = self.client.post("/study-agent/local", json={**body, field_key: wrong_field})
                self.assertEqual(wrong.status_code, 409, wrong.text)
                self.assertFalse(getattr(fake, method).await_count)

                failed = self.client.post("/study-agent/local", json=body)
                self.assertEqual(failed.status_code, 502, failed.text)
                retried = self.client.post("/study-agent/local", json=body)
                self.assertEqual(retried.status_code, 200, retried.text)
                replay = self.client.post("/study-agent/local", json=body)
                self.assertEqual(replay.status_code, 409, replay.text)

    def test_reservation_is_atomic_and_released_on_exception(self):
        used, pending, lock = {}, {}, threading.Lock()
        token = "opaque-signed-token"
        barrier = threading.Barrier(2)

        def contender():
            barrier.wait()
            try:
                reserve(used, pending, lock, token, 4_000_000_000)
                return "reserved"
            except ValueError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(contender), pool.submit(contender)]
            self.assertCountEqual([future.result() for future in futures], ["reserved", "rejected"])
        with self.assertRaises(RuntimeError):
            with use(token, lambda value, *, commit: finish(used, pending, lock, value, commit=commit)):
                raise RuntimeError("provider failed")
        reserve(used, pending, lock, token, 4_000_000_000)
        finish(used, pending, lock, token, commit=True)
        with self.assertRaises(ValueError):
            reserve(used, pending, lock, token, 4_000_000_000)

    def test_concurrent_duplicate_request_is_rejected_while_winner_is_in_flight(self):
        workflow, method, token_key, field_key, expected, prefix, _, token, claims, response_key = self.workflows()[0]
        started, release = threading.Event(), threading.Event()

        async def slow_provider(*_args):
            started.set()
            await asyncio.to_thread(release.wait, 5)
            return {response_key: claims}

        body = {
            "consent": True, "message": "Biology", "context": "", "language": "en",
            "endpoint": self.endpoint, "model_name": "mock-model", "has_api_key": False,
            "workflow": workflow, field_key: expected, token_key: token,
            "messages": [*prefix, "Biology"],
            "scoring_profile_id": "legacy-yks", "scoring_profile_version": 1,
        }
        with patch.object(study_agent, "AIService") as service:
            fake = service.return_value
            fake.base_url = self.endpoint
            setattr(fake, method, slow_provider)
            with ThreadPoolExecutor(max_workers=1) as pool:
                winner = pool.submit(self.client.post, "/study-agent/local", json=body)
                self.assertTrue(started.wait(3), "provider was not reached")
                duplicate = self.client.post("/study-agent/local", json=body)
                self.assertEqual(duplicate.status_code, 409, duplicate.text)
                release.set()
                self.assertEqual(winner.result().status_code, 200)

    def test_learning_and_question_claim_rejection_releases_token_for_corrected_retry(self):
        for workflow, method, token_key, field_key, expected, prefix, _, token, claims, response_key in self.workflows()[3:]:
            with self.subTest(workflow=workflow), patch.object(study_agent, "AIService") as service:
                fake = service.return_value
                fake.base_url = self.endpoint
                bad_claims = [{**claims[0], "quote": "not the current student turn"}]
                setattr(fake, method, AsyncMock(side_effect=[{response_key: bad_claims}, {response_key: claims}]))
                current = "Biology"
                body = {
                    "consent": True, "message": current, "context": "", "language": "en",
                    "endpoint": self.endpoint, "model_name": "mock-model", "has_api_key": False,
                    "workflow": workflow, field_key: expected, token_key: token,
                    "messages": [*prefix, current],
                }
                rejected = self.client.post("/study-agent/local", json=body)
                self.assertEqual(rejected.status_code, 422, rejected.text)
                retried = self.client.post("/study-agent/local", json=body)
                self.assertEqual(retried.status_code, 200, retried.text)
                replay = self.client.post("/study-agent/local", json=body)
                self.assertEqual(replay.status_code, 409, replay.text)


if __name__ == "__main__":
    unittest.main()
