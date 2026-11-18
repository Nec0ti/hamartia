import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_custom_exam import TOOL_NAME


class CustomExamToolAdapterTests(unittest.TestCase):
    def service(self, response):
        create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=response)]))
        service = AIService(model_name="mock-model")
        service._async_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return service, create

    def test_adapter_receives_transcript_and_expected_field_only_and_returns_exact_quote(self):
        message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
            id="custom-tool-call", type="function", function=SimpleNamespace(name=TOOL_NAME,
                arguments=json.dumps({"evidence": [{"field": "section_12_blank", "quote": "7"}]}))
        )])
        service, create = self.service(message)
        result = asyncio.run(service.study_custom_exam_prepare(["7"], "en", "section_12_blank"))
        self.assertEqual(result, {"current_evidence_claims": [{"field": "section_12_blank", "quote": "7"}]})
        request = create.await_args.kwargs
        self.assertIn("only `section_12_blank`", request["messages"][0]["content"])
        self.assertEqual(json.loads(request["messages"][1]["content"]), {"student_messages": ["7"]})
        self.assertEqual(request["tools"][0]["function"]["name"], TOOL_NAME)
        request_text = json.dumps(request).casefold()
        self.assertNotIn("scoring_profile_id", request_text)
        self.assertNotIn("official", request_text)

    def test_adapter_rejects_value_inference_extra_fields_and_wrong_tool(self):
        cases = [
            (json.dumps({"evidence": [{"field": "format_name", "quote": "My mock", "value": "My mock"}]}), TOOL_NAME),
            ('{"evidence":[{"field":"format_name","quote":"My mock"},{"field":"date","quote":"2026-11-19"}]}', TOOL_NAME),
            ('{"evidence":[]}', "wrong-tool"),
        ]
        for arguments, name in cases:
            with self.subTest(arguments=arguments, name=name):
                message = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(
                    id="custom-tool-call", type="function", function=SimpleNamespace(name=name, arguments=arguments)
                )])
                service, _ = self.service(message)
                with self.assertRaises(Exception):
                    asyncio.run(service.study_custom_exam_prepare(["My mock"], "tr", "format_name"))


if __name__ == "__main__":
    unittest.main()
