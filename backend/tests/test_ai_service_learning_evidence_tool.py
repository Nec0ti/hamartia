import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_learning_evidence import PROVIDER_TOOL_NAME


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
    {"field": "date", "quote": MESSAGES[3]},
    {"field": "observation", "quote": MESSAGES[4]},
]


def choice(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments, name=PROVIDER_TOOL_NAME, call_id="learning-call"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class StudyLearningEvidenceToolTests(unittest.TestCase):
    def service(self, responses):
        completions = SimpleNamespace(create=AsyncMock(side_effect=responses))
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        service = AIService(model_name="mock-model")
        service._async_client = client
        return service, completions

    def test_configured_tool_uses_host_expected_field_and_returns_read_only_verified_draft(self):
        responses = [
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({"evidence": CLAIMS}))])),
            choice(SimpleNamespace(content="The exact preview is ready.", tool_calls=None)),
        ]
        service, create = self.service(responses)
        prepared = asyncio.run(service.study_learning_evidence_prepare(MESSAGES, "en", "observation"))
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(prepared["fields"]["subject"], "Biology")
        self.assertFalse(prepared["write_allowed"])
        self.assertEqual(create.create.await_count, 2)
        initial, followup = [call.kwargs for call in create.create.await_args_list]
        tool = initial["tools"][0]["function"]
        self.assertEqual(tool["name"], PROVIDER_TOOL_NAME)
        self.assertIs(tool["strict"], True)
        self.assertEqual(tool["parameters"]["required"], ["evidence"])
        self.assertIs(tool["parameters"]["additionalProperties"], False)
        self.assertIn("currently expects only the `observation` field", initial["messages"][0]["content"])
        self.assertEqual(json.loads(initial["messages"][1]["content"]), {"student_messages": MESSAGES})
        self.assertEqual(followup["messages"][-2]["tool_calls"][0]["id"], "learning-call")
        self.assertEqual(followup["messages"][-1]["tool_call_id"], "learning-call")
        self.assertEqual(followup["tool_choice"], "none")
        self.assertFalse(hasattr(service, "storage"))
        self.assertNotIn("write", json.loads(responses[0].choices[0].message.tool_calls[0].function.arguments))

    def test_invalid_provider_hints_stay_read_only_and_malformed_calls_fail_closed(self):
        out_of_order = [{"field": "subject", "quote": "Biology"}]
        service, create = self.service([
            choice(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps({"evidence": out_of_order}))])),
            choice(SimpleNamespace(content="What activity did you complete?", tool_calls=None)),
        ])
        prepared = asyncio.run(service.study_learning_evidence_prepare(["Biology"], "en", "activity"))
        self.assertEqual(prepared["status"], "incomplete")
        self.assertEqual(prepared["fields"], {})
        self.assertIsNone(prepared["preview_digest"])
        self.assertFalse(hasattr(service, "storage"))
        self.assertEqual(create.create.await_count, 2)

        for args in ("not-json", json.dumps({"evidence": CLAIMS, "write": True})):
            service, create = self.service([
                choice(SimpleNamespace(content=None, tool_calls=[tool_call(args)])),
            ])
            with self.assertRaises(Exception):
                asyncio.run(service.study_learning_evidence_prepare(MESSAGES, "en", "activity"))
            self.assertEqual(create.create.await_count, 1)
            self.assertFalse(hasattr(service, "storage"))


if __name__ == "__main__":
    unittest.main()
