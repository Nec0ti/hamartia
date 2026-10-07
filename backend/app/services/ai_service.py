"""LiteLLM-backed Council of Minds engine.

Wraps the local OpenAI-compatible proxy (`http://localhost:4000/v1`) and turns
a raw failed question into a structured five-counselor + President verdict using
the harness defined in the project root `HAMARTIA.md`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openai import AsyncOpenAI, OpenAIError

from app.core.formulas import net_score
from app.models.schemas import CouncilAnalysis, CouncilVerdict, Question

logger = logging.getLogger("hamartia.ai")
HAMARTIA_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/..

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
        sync_client: bool = False,
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key or "sk-placeholder"
        # Sync client by default so endpoints can be called without an event
        # loop; switch to AsyncOpenAI when streaming is required.
        self.client = OpenAI(base_url=base_url, api_key=self.api_key) if sync_client else None
        self._async_client: AsyncOpenAI | None = None

    # -- lifecycle ----------------------------------------------------------

    async def _ensure_async(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._async_client

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AIService(model={self.model_name!r}, base={self.base_url!r})"

    # -- council pipeline ---------------------------------------------------

    async def analyze_question(self, question: Question) -> CouncilAnalysis:
        """Run the full council over a question and attach the verdict."""
        prompt = self._build_prompt(question)
        raw = await self._completions(prompt)
        envelope = self._parse_envelope(raw)
        analysis = CouncilAnalysis.model_validate(envelope)
        analysis.analyzed_at = question.created_at
        return analysis

    def _build_prompt(self, question: Question) -> list:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Analyze this failed question.\n\n"
                    f"OCR text:\n{question.ocr_text}\n\n"
                    f"Image filename: {question.image_name}"
                ),
            },
        ]

    async def _completions(self, messages: list) -> str:
        try:
            resp = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.2,
            )
            return resp.choices[0].message.content or ""
        except OpenAIError as exc:
            logger.error("LiteLLM council call failed: %s", exc)
            return ""

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
