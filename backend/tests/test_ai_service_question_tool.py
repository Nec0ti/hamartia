import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_question import QUESTION_TOOL_NAME


QUESTION = "If a rectangle has width 4 cm and length 7 cm, what is its area?"


def choice(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments, name=QUESTION_TOOL_NAME, call_id="question-call"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class StudyAgentQuestionToolTests(unittest.TestCase):
    def service(self, responses):
        completions = SimpleNamespace(create=AsyncMock(side_effect=responses))
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        service = AIService(model_name="mock-model")
        service._async_client = client
        return service, completions

    def test_configured_provider_uses_strict_quote_only_tool_and_returns_no_write_draft(self):
        responses = [
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({
                "evidence": [{"field": "question_text", "quote": QUESTION}],
            }))])),
            choice(SimpleNamespace(content="Which subject?", tool_calls=None)),
        ]
        service, create = self.service(responses)
        prepared = asyncio.run(service.study_question_prepare([QUESTION], "en", "question_text"))
        self.assertEqual(prepared["status"], "incomplete")
        self.assertEqual(prepared["expected_field"], "subject")
        self.assertEqual(prepared["current_evidence_claims"], [{"field": "question_text", "quote": QUESTION}])
        self.assertFalse(prepared["write_allowed"])
        self.assertEqual(create.create.await_count, 2)
        initial, followup = [call.kwargs for call in create.create.await_args_list]
        tool = initial["tools"][0]["function"]
        self.assertEqual(tool["name"], QUESTION_TOOL_NAME)
        self.assertIs(tool["strict"], True)
        self.assertEqual(tool["parameters"]["required"], ["evidence"])
        self.assertIs(tool["parameters"]["additionalProperties"], False)
        self.assertEqual(tool["parameters"]["properties"]["evidence"]["maxItems"], 1)
        self.assertIn("entire current student message", initial["messages"][0]["content"])
        self.assertIn("paste the exact problem text as one complete message", initial["messages"][0]["content"])
        self.assertEqual(json.loads(initial["messages"][1]["content"]), {"student_messages": [QUESTION]})
        self.assertEqual(followup["messages"][-2]["tool_calls"][0]["id"], "question-call")
        self.assertEqual(followup["messages"][-1]["tool_call_id"], "question-call")
        self.assertEqual(followup["tool_choice"], "none")
        self.assertFalse(hasattr(service, "storage"))

    def test_configured_provider_uses_host_verified_prior_claims_for_next_turn(self):
        messages = [QUESTION, "Biology", "Geometry"]
        prior = [
            {"field": "question_text", "quote": QUESTION},
            {"field": "subject", "quote": "Biology"},
        ]
        current = {"field": "topic", "quote": "Geometry"}
        service, create = self.service([
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({"evidence": [current]}))])),
            choice(SimpleNamespace(content="The exact preview is ready.", tool_calls=None)),
        ])
        prepared = asyncio.run(service.study_question_prepare(messages, "en", "topic", prior))
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(prepared["fields"], {"question_text": QUESTION, "subject": "Biology", "topic": "Geometry"})
        self.assertEqual(prepared["current_evidence_claims"], [current])
        self.assertEqual(prepared["verified_evidence"]["topic"]["quote"], "Geometry")
        self.assertEqual(json.loads(create.create.await_args_list[1].kwargs["messages"][-1]["content"])["fields"], prepared["fields"])

    def test_configured_provider_rejects_extra_values_unknown_fields_and_extra_tool_calls(self):
        bad_args = [
            {"evidence": [{"field": "question_text", "quote": QUESTION, "value": QUESTION}]},
            {"evidence": [{"field": "record_id", "quote": "q_1"}]},
            {"evidence": [{"field": "question_text", "quote": QUESTION}, {"field": "subject", "quote": "Biology"}]},
        ]
        for args in bad_args:
            with self.subTest(args=args):
                service, create = self.service([choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps(args))]))])
                with self.assertRaises(Exception):
                    asyncio.run(service.study_question_prepare([QUESTION], "en", "question_text"))
                self.assertEqual(create.create.await_count, 1)
                self.assertFalse(hasattr(service, "storage"))

        service, create = self.service([
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({"evidence": []}))])),
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({"evidence": []}), name="second")])),
        ])
        with self.assertRaisesRegex(ValueError, "additional question-capture tool call"):
            asyncio.run(service.study_question_prepare([QUESTION], "en", "question_text"))
        self.assertEqual(create.create.await_count, 2)


if __name__ == "__main__":
    unittest.main()
