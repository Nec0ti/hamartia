import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.ai_service import AIService
from app.services.study_agent_sectioned_exam import TOOL_NAME


def response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(arguments, name=TOOL_NAME):
    return SimpleNamespace(id="sectioned-call", type="function", function=SimpleNamespace(name=name, arguments=arguments))


class SectionedExamProviderAdapterTests(unittest.TestCase):
    def service(self, messages):
        create = AsyncMock(side_effect=messages)
        service = AIService(model_name="mock-model")
        service._async_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return service, create

    def test_configured_provider_receives_only_transcript_and_expected_quote_field(self):
        service, create = self.service([response(SimpleNamespace(content=None, tool_calls=[
            tool_call(json.dumps({"evidence": [{"field": "section_6_blank", "quote": "42"}]})),
        ]))])
        result = asyncio.run(service.study_sectioned_exam_prepare(["42"], "tr", "section_6_blank"))
        self.assertEqual(result, {"current_evidence_claims": [{"field": "section_6_blank", "quote": "42"}]})
        request = create.await_args.kwargs
        self.assertEqual(request["tools"][0]["function"]["name"], TOOL_NAME)
        self.assertEqual(json.loads(request["messages"][1]["content"]), {"student_messages": ["42"]})
        self.assertIn("only `section_6_blank`", request["messages"][0]["content"])
        self.assertNotIn("legacy-yks", json.dumps(request).casefold())
        self.assertNotIn("profile_id", json.dumps(request).casefold())
        args = request["tools"][0]["function"]["parameters"]
        self.assertEqual(set(args["properties"]["evidence"]["items"]["properties"]), {"field", "quote"})

    def test_configured_provider_rejects_values_extra_hints_or_wrong_tool(self):
        invalid = [
            {"evidence": [{"field": "exam_type", "quote": "TYT", "value": "tyt"}]},
            {"evidence": [{"field": "exam_type", "quote": "TYT"}, {"field": "date", "quote": "2026-11-16"}]},
        ]
        for arguments in invalid:
            service, _ = self.service([response(SimpleNamespace(content=None, tool_calls=[tool_call(json.dumps(arguments))]))])
            with self.assertRaises(Exception):
                asyncio.run(service.study_sectioned_exam_prepare(["TYT"], "en", "exam_type"))
        service, _ = self.service([response(SimpleNamespace(content=None, tool_calls=[tool_call('{"evidence":[]}', "wrong-tool")]))])
        with self.assertRaises(ValueError):
            asyncio.run(service.study_sectioned_exam_prepare(["TYT"], "en", "exam_type"))


if __name__ == "__main__":
    unittest.main()
