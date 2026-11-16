"""Short-lived, one-use snapshots for question-analysis consent."""

from dataclasses import dataclass
import threading
import time
from typing import Any
from uuid import uuid4

from app.models.schemas import Question
from app.services.ai_service import AIService

CONSENT_TTL_SECONDS = 300
MAX_PENDING_CONSENTS = 128


@dataclass(frozen=True)
class QuestionAnalysisSnapshot:
    consent_id: str
    question_id: str
    question: Question
    ai: AIService
    prompt: list[dict[str, Any]]
    fingerprint: str
    expires_at: float


class QuestionAnalysisConsentRegistry:
    """Process-local because the packaged API runs as one loopback worker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, QuestionAnalysisSnapshot] = {}

    def issue(
        self,
        *,
        question: Question,
        ai: AIService,
        prompt: list[dict[str, Any]],
        fingerprint: str,
    ) -> QuestionAnalysisSnapshot:
        now = time.monotonic()
        consent_id = uuid4().hex
        snapshot = QuestionAnalysisSnapshot(
            consent_id=consent_id,
            question_id=question.id,
            question=question.model_copy(deep=True),
            ai=ai,
            prompt=prompt,
            fingerprint=fingerprint,
            expires_at=now + CONSENT_TTL_SECONDS,
        )
        with self._lock:
            self._prune(now)
            if len(self._snapshots) >= MAX_PENDING_CONSENTS:
                oldest = min(self._snapshots.values(), key=lambda item: item.expires_at)
                self._snapshots.pop(oldest.consent_id, None)
            self._snapshots[consent_id] = snapshot
        return snapshot

    def consume(self, consent_id: str, question_id: str) -> QuestionAnalysisSnapshot | None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            snapshot = self._snapshots.pop(consent_id, None)
            if snapshot is None or snapshot.question_id != question_id:
                return None
            return snapshot

    def discard(self, consent_id: str) -> None:
        with self._lock:
            self._snapshots.pop(consent_id, None)

    def _prune(self, now: float) -> None:
        expired = [key for key, value in self._snapshots.items() if value.expires_at <= now]
        for key in expired:
            self._snapshots.pop(key, None)


question_analysis_consents = QuestionAnalysisConsentRegistry()
