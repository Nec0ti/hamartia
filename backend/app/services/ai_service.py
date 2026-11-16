"""LiteLLM-backed Council of Minds engine.

Wraps the local OpenAI-compatible proxy (`http://localhost:4000/v1`) and turns
a raw failed question into a structured five-counselor + President verdict using
the harness defined in the project root `HAMARTIA.md`.
"""

from __future__ import annotations

import json
from base64 import b64encode
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import DATA_DIR
from app.core.formulas import net_score
from app.models.schemas import CouncilAnalysis, CouncilVerdict, Question, Settings
from app.services.storage import StorageService
from app.services.study_agent_cli import PROVIDER_TOOL_NAME, dispatch_provider_tool, provider_tool_parameters
from app.services.study_agent_learning_evidence import (
    PROVIDER_TOOL_NAME as LEARNING_EVIDENCE_TOOL_NAME,
    ProviderToolArguments as LearningEvidenceToolArguments,
    dispatch_provider_tool as dispatch_learning_evidence_tool,
    provider_tool_parameters as learning_evidence_tool_parameters,
)
from app.services.study_agent_question import (
    QUESTION_TOOL_NAME,
    QuestionToolArguments,
    prepare_question_capture,
    provider_tool_parameters as question_tool_parameters,
)
from app.services.study_agent_exam import (
    EXAM_TOOL_NAME,
    ExamToolArguments,
    provider_tool_parameters as exam_tool_parameters,
)
from app.services.upload_paths import UnsafeUploadPath, resolve_question_image

HAMARTIA_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/..
IMAGE_MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_QUESTION_IMAGE_BYTES = 10 * 1024 * 1024


class QuestionAnalysisPayloadTooLarge(ValueError):
    """A legacy or changed saved image exceeds the safe analysis input limit."""

# System prompt distilled from HAMARTIA.md. Injected at runtime so the harness
# stays the single source of truth for the council's behavior.
SYSTEM_PROMPT = (
    "You are the President of the Council of Minds for Hamartia, an AI mistake "
    "diagnostic engine for competitive exam students. Five counselors analyze a "
    "single failed question. You orchestrate their reasoning and emit one JSON "
    "verdict. Counselors: Dissenter (trap + false assumptions), First Principles "
    "(foundational deconstruction), Expansionist (hidden meta-rules), Outsider "
    "(surface careless oversights), Executor (one actionable mnemonic). Assign "
    "exactly one hamartia_tag from: [Distractor Trap], [Knowledge Gap], "
    "[Reading Slip], [Time Panic]. Answer in English. Never emit emojis. "
    "Never break the JSON envelope."
)

# Allowed tag taxonomy (kept in sync with the harness roster).
TAGS = [
    "[Distractor Trap]",
    "[Knowledge Gap]",
    "[Reading Slip]",
    "[Time Panic]",
]


class AIService:
    def __init__(
        self,
        base_url: str = "http://localhost:4000/v1",
        model_name: str = "ollama/qwen2.5",
        api_key: str = "",
        max_retries: int = 2,
        http_client=None,
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key or "sk-placeholder"
        self.max_retries = max_retries
        self._http_client = http_client
        self._async_client: AsyncOpenAI | None = None

    @classmethod
    def default(cls) -> "AIService":
        """Factory using the locally saved model endpoint and credentials."""
        settings = StorageService(DATA_DIR).load_doc("settings.json", Settings) or Settings()
        return cls(
            base_url=settings.litellm_base_url,
            model_name=settings.model_name,
            api_key=settings.api_key,
        )

    # -- lifecycle ----------------------------------------------------------

    async def _ensure_async(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                max_retries=self.max_retries,
                http_client=self._http_client,
            )
        return self._async_client

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AIService(model={self.model_name!r}, base={self.base_url!r})"

    async def analyze_question(self, question: Question, prompt: list | None = None) -> CouncilAnalysis:
        """Run the full council over a question and attach the verdict."""
        request_prompt = prompt if prompt is not None else self._build_prompt(question)
        raw = await self._completions(request_prompt)
        envelope = self._parse_envelope(raw)
        analysis = CouncilAnalysis.model_validate(envelope)
        analysis.analyzed_at = question.created_at
        return analysis

    async def study_chat(self, message: str, context: str, language: str) -> str:
        """Answer a Study Agent request without applying the Council prompt."""
        client = await self._ensure_async()
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Hamartia's study assistant. Answer in "
                        f"{'Turkish' if language == 'tr' else 'English'}. Use only the supplied "
                        "student message and bounded study summary. Do not claim to have seen "
                        "specific question text, images, or conversations. Identify mistake patterns "
                        "only when the summary supports them; say when evidence is insufficient. "
                        "Curriculum references are user-entered and unverified, not official alignment. "
                        "If one is present, relate it cautiously and label it as user-provided. "
                        "Suggest a concrete next learning activity and a separate evidence-of-learning "
                        "task with observable success criteria. Use short localized sections for "
                        "supported pattern, next activity, evidence task, and criteria. Do not infer "
                        "mastery from one response, equate "
                        "learning evidence with exam net or XP, or claim an evidence task has been "
                        "completed. Without a reference, do not invent a curriculum mapping. "
                        "Be clear and concise."
                    ),
                },
                {"role": "user", "content": f"Local study summary (may be empty):\n{context}\n\nStudent question:\n{message}"},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content:
            raise ValueError("The configured endpoint returned an empty response.")
        return content

    async def study_practice_prepare(self, messages: list[str], language: str) -> dict:
        """Run one evidence-only Chat Completions tool cycle and verify quotes locally."""
        client = await self._ensure_async()
        system = (
            "You are the Hamartia practice-entry evidence assistant. Use the one available tool exactly once. "
            "The tool accepts only exact evidence quotes from the supplied student messages; it does not accept "
            "values, record IDs, transcript text, paths, or write instructions. Return quotes that support each "
            "practice field and omit fields without clear evidence. Never guess, calculate, resolve conflicts, "
            "or paraphrase a quote. After the verified tool result, ask the localized question it supplies or "
            "briefly acknowledge that a verified preview is ready. Answer in "
            f"{'Turkish' if language == 'tr' else 'English'}."
        )
        transcript = {"role": "user", "content": json.dumps({"student_messages": messages}, ensure_ascii=False)}
        function_tool = {
            "type": "function",
            "function": {
                "name": PROVIDER_TOOL_NAME,
                "description": "Submit exact student-message quotes for local verification and a read-only practice preview.",
                "parameters": provider_tool_parameters(),
                "strict": True,
            },
        }
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system}, transcript],
            tools=[function_tool],
            tool_choice={"type": "function", "function": {"name": PROVIDER_TOOL_NAME}},
            parallel_tool_calls=False,
            temperature=0,
        )
        message = response.choices[0].message
        calls = message.tool_calls or []
        if message.content not in (None, "") or len(calls) != 1:
            raise ValueError("The configured endpoint did not return exactly one evidence tool call.")
        call = calls[0]
        if call.type != "function" or call.function.name != PROVIDER_TOOL_NAME or not call.id:
            raise ValueError("The configured endpoint returned an unsupported tool call.")
        try:
            arguments = json.loads(call.function.arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The configured endpoint returned malformed evidence arguments.") from exc
        prepared = dispatch_provider_tool(arguments, messages=messages, language=language)
        tool_result = {
            key: prepared[key]
            for key in ("status", "fields", "verified_evidence", "missing", "ambiguous", "questions", "preview_digest", "write_allowed")
        }
        followup = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                transcript,
                {"role": "assistant", "tool_calls": [{
                    "id": call.id,
                    "type": "function",
                    "function": {"name": PROVIDER_TOOL_NAME, "arguments": call.function.arguments},
                }]},
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_result, ensure_ascii=False)},
            ],
            tools=[function_tool],
            tool_choice="none",
            parallel_tool_calls=False,
            temperature=0,
        )
        final_message = followup.choices[0].message
        if final_message.tool_calls:
            raise ValueError("The configured endpoint attempted an additional tool call.")
        return prepared

    async def study_learning_evidence_prepare(
        self, messages: list[str], language: str, expected_field: str = "activity",
        prior_evidence_claims: list[dict] | None = None,
    ) -> dict:
        """Run an evidence-only tool cycle for one user-reported completed activity."""
        client = await self._ensure_async()
        system = (
            "You are Hamartia's learning-evidence preparation assistant. Use the one available tool exactly once. "
            "The tool accepts only exact quotes from student messages and field names; it does not accept values, "
            "record IDs, transcript text, language, paths, completion flags, or write instructions. "
            f"The host currently expects only the `{expected_field}` field; quote only that field. Never infer completion, mastery, a date, "
            "a URL, or any value; do not paraphrase. A completed activity must be stated by the student as an "
            "affirmative completed action. After the verified tool result, ask only the localized question it "
            "supplies or briefly say the exact preview is ready. Answer in "
            f"{'Turkish' if language == 'tr' else 'English'}."
        )
        transcript = {"role": "user", "content": json.dumps({"student_messages": messages}, ensure_ascii=False)}
        function_tool = {
            "type": "function",
            "function": {
                "name": LEARNING_EVIDENCE_TOOL_NAME,
                "description": "Submit an exact quote for the currently expected learning-evidence field; read-only preview only.",
                "parameters": learning_evidence_tool_parameters(),
                "strict": True,
            },
        }
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system}, transcript],
            tools=[function_tool],
            tool_choice={"type": "function", "function": {"name": LEARNING_EVIDENCE_TOOL_NAME}},
            parallel_tool_calls=False,
            temperature=0,
        )
        message = response.choices[0].message
        calls = message.tool_calls or []
        if message.content not in (None, "") or len(calls) != 1:
            raise ValueError("The configured endpoint did not return exactly one learning-evidence tool call.")
        call = calls[0]
        if call.type != "function" or call.function.name != LEARNING_EVIDENCE_TOOL_NAME or not call.id:
            raise ValueError("The configured endpoint returned an unsupported learning-evidence tool call.")
        try:
            arguments = json.loads(call.function.arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The configured endpoint returned malformed learning-evidence arguments.") from exc
        tool_arguments = LearningEvidenceToolArguments.model_validate(arguments)
        current_claims = [item.model_dump() for item in tool_arguments.evidence]
        prepared = dispatch_learning_evidence_tool(
            {"evidence": [*(prior_evidence_claims or []), *current_claims]},
            messages=messages, language=language,
        )
        tool_result = {
            key: prepared[key]
            for key in ("status", "fields", "verified_evidence", "missing", "ambiguous", "questions", "preview_digest", "write_allowed")
        }
        followup = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                transcript,
                {"role": "assistant", "tool_calls": [{
                    "id": call.id,
                    "type": "function",
                    "function": {"name": LEARNING_EVIDENCE_TOOL_NAME, "arguments": call.function.arguments},
                }]},
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_result, ensure_ascii=False)},
            ],
            tools=[function_tool],
            tool_choice="none",
            parallel_tool_calls=False,
            temperature=0,
        )
        final_message = followup.choices[0].message
        if final_message.tool_calls:
            raise ValueError("The configured endpoint attempted an additional learning-evidence tool call.")
        prepared["evidence_claims"] = current_claims
        return prepared

    async def study_question_prepare(
        self, messages: list[str], language: str, expected_field: str,
        prior_question_claims: list[dict] | None = None,
    ) -> dict:
        """Run an evidence-only tool cycle for text-only missed-question capture."""
        client = await self._ensure_async()
        system = (
            "You are Hamartia's missed-question capture assistant. Use the one available tool exactly once. "
            f"The host currently expects only `{expected_field}`. Provide one exact quote that is the entire current student message, "
            "with that field name. For question_text, ask the student to paste the exact problem text as one complete message and not summarize it. "
            "For subject/topic, quote only the exact answer in the current turn; if unknown, quote the student's explicit skip reply. "
            "Do not send values, IDs, tags, analysis, curriculum metadata, images, URLs, or write instructions. Never guess or paraphrase. "
            "After verification, ask only the localized host follow-up or briefly say the exact preview is ready. Answer in "
            f"{'Turkish' if language == 'tr' else 'English'}."
        )
        transcript = {"role": "user", "content": json.dumps({"student_messages": messages}, ensure_ascii=False)}
        function_tool = {
            "type": "function",
            "function": {
                "name": QUESTION_TOOL_NAME,
                "description": "Submit one exact current-turn quote for host verification and a read-only question preview.",
                "parameters": question_tool_parameters(),
                "strict": True,
            },
        }
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system}, transcript],
            tools=[function_tool],
            tool_choice={"type": "function", "function": {"name": QUESTION_TOOL_NAME}},
            parallel_tool_calls=False,
            temperature=0,
        )
        message = response.choices[0].message
        calls = message.tool_calls or []
        if message.content not in (None, "") or len(calls) != 1:
            raise ValueError("The configured endpoint did not return exactly one question-capture tool call.")
        call = calls[0]
        if call.type != "function" or call.function.name != QUESTION_TOOL_NAME or not call.id:
            raise ValueError("The configured endpoint returned an unsupported question-capture tool call.")
        try:
            arguments = json.loads(call.function.arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The configured endpoint returned malformed question-capture arguments.") from exc
        tool_args = QuestionToolArguments.model_validate(arguments)
        current_claims = [item.model_dump() for item in tool_args.evidence]
        prepared = prepare_question_capture(messages, language, [*(prior_question_claims or []), *current_claims])
        prepared["current_evidence_claims"] = current_claims
        tool_result = {
            key: prepared[key]
            for key in ("status", "fields", "verified_evidence", "missing", "ambiguous", "questions", "preview_digest", "write_allowed")
        }
        followup = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                transcript,
                {"role": "assistant", "tool_calls": [{
                    "id": call.id,
                    "type": "function",
                    "function": {"name": QUESTION_TOOL_NAME, "arguments": call.function.arguments},
                }]},
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_result, ensure_ascii=False)},
            ],
            tools=[function_tool],
            tool_choice="none",
            parallel_tool_calls=False,
            temperature=0,
        )
        final_message = followup.choices[0].message
        if final_message.tool_calls:
            raise ValueError("The configured endpoint attempted an additional question-capture tool call.")
        return prepared

    async def study_exam_prepare(self, messages: list[str], language: str, expected_field: str) -> dict:
        """Request only one exact current-turn exam quote from the configured provider."""
        client = await self._ensure_async()
        system = (
            "You are Hamartia's branch-exam evidence assistant. Use the one available tool exactly once. "
            f"The host currently expects only `{expected_field}`. Submit one exact quote that is the entire newest student message, "
            "with that field name. The host will parse the value using the field-specific prompt; never send a value, date inference, "
            "exam type, scoring profile, ID, net, XP, transcript modification, or write instruction. "
            "Do not guess, normalize, paraphrase, or use an earlier turn. If the newest turn is unclear, return an empty evidence list. "
            "Answer in " + ("Turkish" if language == "tr" else "English") + "."
        )
        transcript = {"role": "user", "content": json.dumps({"student_messages": messages}, ensure_ascii=False)}
        function_tool = {
            "type": "function",
            "function": {
                "name": EXAM_TOOL_NAME,
                "description": "Submit one exact current-turn quote for host verification and a read-only branch-exam preview.",
                "parameters": exam_tool_parameters(),
                "strict": True,
            },
        }
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": system}, transcript],
            tools=[function_tool],
            tool_choice={"type": "function", "function": {"name": EXAM_TOOL_NAME}},
            parallel_tool_calls=False,
            temperature=0,
        )
        message = response.choices[0].message
        calls = message.tool_calls or []
        if message.content not in (None, "") or len(calls) != 1:
            raise ValueError("The configured endpoint did not return exactly one exam evidence tool call.")
        call = calls[0]
        if call.type != "function" or call.function.name != EXAM_TOOL_NAME or not call.id:
            raise ValueError("The configured endpoint returned an unsupported exam tool call.")
        try:
            arguments = json.loads(call.function.arguments)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("The configured endpoint returned malformed exam evidence arguments.") from exc
        tool_arguments = ExamToolArguments.model_validate(arguments)
        return {"current_evidence_claims": [item.model_dump() for item in tool_arguments.evidence]}

    def _build_prompt(self, question: Question, data_dir: Path | None = None) -> list:
        content = [{
            "type": "text",
            "text": (
                f"Analyze this failed question.\n\n"
                f"OCR text:\n{question.ocr_text}\n\n"
                f"Image filename: {question.image_name}"
            ),
        }]
        try:
            image_path = resolve_question_image(data_dir or DATA_DIR, question.image_path)
        except UnsafeUploadPath:
            image_path = None
        mime_type = IMAGE_MIME_TYPES.get(Path(question.image_name).suffix.lower())
        if mime_type and image_path and image_path.is_file():
            with image_path.open("rb") as image_file:
                image_bytes = image_file.read(MAX_QUESTION_IMAGE_BYTES + 1)
            if len(image_bytes) > MAX_QUESTION_IMAGE_BYTES:
                raise QuestionAnalysisPayloadTooLarge("Saved question image exceeds the analysis limit")
            encoded = b64encode(image_bytes).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}})
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

    async def _completions(self, messages: list) -> str:
        client = await self._ensure_async()
        resp = await client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    # -- parsing ------------------------------------------------------------

    def _parse_envelope(self, raw: str) -> dict:
        """Extract the JSON envelope from the model text, tolerating chatter.

        Falls back to a safe default verdict if the model returns garbage so
        the API never 500s on an unstructured LLM response.
        """
        raw = (raw or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end < start:
            return self._default_envelope()
        candidate = raw[start : end + 1]
        try:
            parsed = json.loads(candidate)
            return parsed
        except ValueError:
            return self._default_envelope()

    def _default_envelope(self) -> dict:
        return {
            "counselors": {k: "" for k in ["dissenter", "first_principles", "expansionist", "outsider", "executor"]},
            "verdict": {
                "hamartia_tag": TAGS[0],
                "root_cause": "Model unavailable; review the question manually.",
                "action_advice": "Re-attempt after a short break.",
                "difficulty": 3,
                "subject_affinity": "",
            },
        }

    @staticmethod
    def normalize_tag(tag: str) -> str:
        """Coerce an arbitrary tag string into the allowed taxonomy."""
        cleaned = tag.strip().strip("[]").strip()
        for allowed in TAGS:
            if cleaned.lower() in allowed.lower():
                return allowed
        return TAGS[0]


# Shared dependency provider so routers can request the default council engine
# without manually constructing it.
def get_ai() -> AIService:
    """Return the default sync-backed council engine (singleton)."""
    return AIService.default()
