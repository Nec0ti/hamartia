import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_cli import PROVIDER_TOOL_NAME


MESSAGES = [
    "I completed a practice test on Functions in Mathematics on 2026-11-15. "
    "I got 12 right, 3 wrong, left 1 blank; it took 45 minutes and 0 seconds."
]
EVIDENCE = [
    {"field": "subject", "quote": "in Mathematics"},
    {"field": "topic", "quote": "on Functions"},
    {"field": "date", "quote": "on 2026-11-15"},
    {"field": "correct", "quote": "12 right"},
    {"field": "incorrect", "quote": "3 wrong"},
    {"field": "blank", "quote": "left 1 blank"},
    {"field": "duration_minutes", "quote": "it took 45 minutes"},
    {"field": "duration_seconds", "quote": "0 seconds"},
]


def choice(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def function_call(arguments, name=PROVIDER_TOOL_NAME, call_id="call_1"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def tool_message(arguments, name=PROVIDER_TOOL_NAME):
    return SimpleNamespace(content=None, tool_calls=[function_call(arguments, name=name)])


class StudyPracticeCompletionsToolTests(unittest.TestCase):
    def service(self, responses):
        completions = SimpleNamespace(create=AsyncMock(side_effect=responses))
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        service = AIService(model_name="mock-model")
        service._async_client = client
        return service, completions

    def test_strict_quote_tool_returns_locally_verified_draft_and_executes_call_id(self):
        responses = [choice(tool_message(json.dumps({"evidence": EVIDENCE}))), choice(SimpleNamespace(content="Please review this preview.", tool_calls=None))]
        service, create = self.service(responses)
        result = asyncio.run(service.study_practice_prepare(MESSAGES, "en"))

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fields"]["correct"], 12)
        self.assertFalse(result["write_allowed"])
        self.assertEqual(create.create.await_count, 2)
        initial, followup = [call.kwargs for call in create.create.await_args_list]
        tool = initial["tools"][0]["function"]
        self.assertEqual(tool["name"], PROVIDER_TOOL_NAME)
        self.assertIs(tool["strict"], True)
        self.assertEqual(tool["parameters"]["required"], ["evidence"])
        self.assertIs(tool["parameters"]["additionalProperties"], False)
        self.assertEqual(initial["tool_choice"]["function"]["name"], PROVIDER_TOOL_NAME)
        self.assertIs(initial["parallel_tool_calls"], False)
        self.assertEqual(json.loads(initial["messages"][1]["content"]), {"student_messages": MESSAGES})
        self.assertEqual(json.loads(followup["messages"][1]["content"]), {"student_messages": MESSAGES})
        self.assertEqual(followup["messages"][-2]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(followup["messages"][-1]["tool_call_id"], "call_1")
        self.assertEqual(followup["tool_choice"], "none")
        self.assertNotIn("previous_response_id", initial)
        self.assertNotIn("messages", json.loads(responses[0].choices[0].message.tool_calls[0].function.arguments))

    def test_malformed_partial_unsupported_and_value_bearing_tool_calls_fail_closed(self):
        bad_arguments = [
            "not-json",
            json.dumps({}),
            json.dumps({"evidence": EVIDENCE, "messages": MESSAGES}),
            json.dumps({"evidence": [{"field": "correct", "quote": "12 right", "value": 12}]}),
        ]
        for arguments in bad_arguments:
            with self.subTest(arguments=arguments):
                service, create = self.service([choice(tool_message(arguments))])
                with self.assertRaises(Exception):
                    asyncio.run(service.study_practice_prepare(MESSAGES, "en"))
                self.assertEqual(create.create.await_count, 1)

        service, _ = self.service([choice(tool_message(json.dumps({"evidence": EVIDENCE}), name="write_record"))])
        with self.assertRaisesRegex(ValueError, "unsupported tool"):
            asyncio.run(service.study_practice_prepare(MESSAGES, "en"))

    def test_text_only_or_additional_tool_response_is_rejected(self):
        service, _ = self.service([choice(SimpleNamespace(content="I guessed all fields.", tool_calls=None))])
        with self.assertRaisesRegex(ValueError, "exactly one evidence tool"):
            asyncio.run(service.study_practice_prepare(MESSAGES, "en"))

        first = choice(tool_message(json.dumps({"evidence": EVIDENCE})))
        second = choice(SimpleNamespace(content=None, tool_calls=[function_call("{}", call_id="call_2")]))
        service, create = self.service([first, second])
        with self.assertRaisesRegex(ValueError, "additional tool call"):
            asyncio.run(service.study_practice_prepare(MESSAGES, "en"))
        self.assertEqual(create.create.await_count, 2)

    def test_provider_exception_propagates_without_any_storage_capability(self):
        service, create = self.service([RuntimeError("mock provider offline")])
        with self.assertRaisesRegex(RuntimeError, "mock provider offline"):
            asyncio.run(service.study_practice_prepare(MESSAGES, "en"))
        self.assertEqual(create.create.await_count, 1)
        self.assertFalse(hasattr(service, "storage"))


if __name__ == "__main__":
    unittest.main()
