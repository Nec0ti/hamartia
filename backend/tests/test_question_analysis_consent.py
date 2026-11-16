import asyncio
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAIError

from app.models.schemas import Question
from app.services.ai_service import AIService
from app.services.question_analysis_consent import (
    CONSENT_TTL_SECONDS,
    MAX_PENDING_CONSENTS,
    MAX_PENDING_CONSENT_BYTES,
    QuestionAnalysisConsentRegistry,
)


class QuestionAnalysisConsentRegistryTests(unittest.TestCase):
    def issue(self, registry, question_id="q1", prompt=None):
        question = Question(id=question_id, ocr_text="synthetic")
        ai = AIService()
        return registry.issue(
            question=question,
            ai=ai,
            prompt=prompt if prompt is not None else ai._build_prompt(question),
            fingerprint="synthetic-fingerprint",
        )

    def test_snapshot_expires_and_cannot_be_consumed(self):
        registry = QuestionAnalysisConsentRegistry()
        with patch("app.services.question_analysis_consent.time.monotonic", return_value=1000):
            snapshot = self.issue(registry)
        self.assertEqual(snapshot.expires_at, 1000 + CONSENT_TTL_SECONDS)

        with patch("app.services.question_analysis_consent.time.monotonic", return_value=1000 + CONSENT_TTL_SECONDS):
            self.assertIsNone(registry.consume(snapshot.consent_id, "q1"))

    def test_registry_evicts_oldest_pending_snapshot_at_capacity(self):
        registry = QuestionAnalysisConsentRegistry()
        with patch("app.services.question_analysis_consent.time.monotonic", side_effect=range(MAX_PENDING_CONSENTS + 1)):
            snapshots = [self.issue(registry, f"q{index}") for index in range(MAX_PENDING_CONSENTS + 1)]

        with patch("app.services.question_analysis_consent.time.monotonic", return_value=MAX_PENDING_CONSENTS + 1):
            self.assertIsNone(registry.consume(snapshots[0].consent_id, "q0"))
            self.assertIsNotNone(registry.consume(snapshots[-1].consent_id, f"q{MAX_PENDING_CONSENTS}"))

    def test_registry_evicts_oldest_snapshots_to_stay_within_byte_budget(self):
        registry = QuestionAnalysisConsentRegistry()
        prompt_size = 13 * 1024 * 1024
        prompt = [{"role": "user", "content": "x" * prompt_size}]
        with patch("app.services.question_analysis_consent.time.monotonic", side_effect=(100, 101, 102)):
            snapshots = [self.issue(registry, f"q{index}", prompt) for index in range(3)]

        self.assertLessEqual(
            sum(snapshot.size_bytes for snapshot in registry._snapshots.values()),
            MAX_PENDING_CONSENT_BYTES,
        )
        with patch("app.services.question_analysis_consent.time.monotonic", return_value=103):
            self.assertIsNone(registry.consume(snapshots[0].consent_id, "q0"))
            self.assertIsNotNone(registry.consume(snapshots[-1].consent_id, "q2"))

    def test_preview_admission_bounds_concurrent_prompt_assembly(self):
        registry = QuestionAnalysisConsentRegistry()
        self.assertTrue(registry.begin_preview())
        self.assertTrue(registry.begin_preview())
        self.assertFalse(registry.begin_preview())
        registry.end_preview()
        self.assertTrue(registry.begin_preview())
        registry.end_preview()
        registry.end_preview()
        registry.end_preview()

    def test_question_analysis_transport_makes_one_attempt_on_failure(self):
        attempts = []

        async def fail_once(request):
            attempts.append(request)
            raise httpx.ConnectError("synthetic transport failure", request=request)

        async def run():
            client = httpx.AsyncClient(transport=httpx.MockTransport(fail_once))
            try:
                ai = AIService(
                    base_url="https://example.test/v1",
                    model_name="fixture-model",
                    api_key="synthetic-secret",
                    max_retries=0,
                    http_client=client,
                )
                with self.assertRaises(OpenAIError):
                    await ai._completions([{"role": "user", "content": "synthetic"}])
            finally:
                await client.aclose()

        asyncio.run(run())
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
