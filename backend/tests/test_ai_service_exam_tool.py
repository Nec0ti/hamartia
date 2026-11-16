import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_exam import EXAM_TOOL_NAME


def choice(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments, name=EXAM_TOOL_NAME, call_id="exam-call"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class StudyAgentExamProviderTests(unittest.TestCase):
    def service(self, responses):
        completions = SimpleNamespace(create=AsyncMock(side_effect=responses))
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        service = AIService(model_name="mock-model")
        service._async_client = client
        return service, completions

    def test_configured_provider_receives_only_expected_field_and_returns_quote_hint(self):
        service, create = self.service([choice(SimpleNamespace(
            content=None,
            tool_calls=[tool_call(json.dumps({"evidence": [{"field": "date", "quote": "2026-11-16"}]}))],
        ))])
        prepared = asyncio.run(service.study_exam_prepare(["2026-11-16"], "en", "date"))
        self.assertEqual(prepared, {"current_evidence_claims": [{"field": "date", "quote": "2026-11-16"}]})
        self.assertEqual(create.create.await_count, 1)
        request = create.create.await_args.kwargs
        self.assertEqual(request["tools"][0]["function"]["name"], EXAM_TOOL_NAME)
        params = request["tools"][0]["function"]["parameters"]
        self.assertEqual(params["properties"]["evidence"]["items"]["required"], ["field", "quote"])
        self.assertEqual(set(params["properties"]["evidence"]["items"]["properties"]), {"field", "quote"})
        self.assertIn("only `date`", request["messages"][0]["content"])
        self.assertEqual(json.loads(request["messages"][1]["content"]), {"student_messages": ["2026-11-16"]})
        self.assertNotIn("scoring_profile", json.dumps(request))

    def test_configured_provider_rejects_values_unknown_fields_and_multiple_hints(self):
        for args in (
            {"evidence": [{"field": "correct", "quote": "25", "value": 25}]},
            {"evidence": [{"field": "exam_type", "quote": "branch"}]},
            {"evidence": [{"field": "correct", "quote": "25"}, {"field": "incorrect", "quote": "3"}]},
        ):
            with self.subTest(args=args):
                service, create = self.service([choice(SimpleNamespace(
                    content=None, tool_calls=[tool_call(json.dumps(args))],
                ))])
                with self.assertRaises(Exception):
                    asyncio.run(service.study_exam_prepare(["25"], "en", "correct"))
                self.assertEqual(create.create.await_count, 1)

    def test_configured_provider_rejects_content_extra_call_or_wrong_tool_name(self):
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="guessed 25", tool_calls=[tool_call('{"evidence": []}')]))]),
            choice(SimpleNamespace(content=None, tool_calls=[tool_call('{"evidence": []}', name="other_tool")])),
            choice(SimpleNamespace(content=None, tool_calls=[tool_call('{"evidence": []}'), tool_call('{"evidence": []}', call_id="second")])),
        ]
        for response in responses:
            service, _ = self.service([response])
            with self.assertRaises(ValueError):
                asyncio.run(service.study_exam_prepare(["25"], "en", "correct"))


if __name__ == "__main__":
    unittest.main()
