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
    QuestionAnalysisConsentRegistry,
)


class QuestionAnalysisConsentRegistryTests(unittest.TestCase):
    def issue(self, registry, question_id="q1"):
        question = Question(id=question_id, ocr_text="synthetic")
        ai = AIService()
        return registry.issue(
            question=question,
            ai=ai,
            prompt=ai._build_prompt(question),
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
