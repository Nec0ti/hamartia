"""Short-lived, one-use snapshots for question-analysis consent."""

from dataclasses import dataclass
import json
import threading
import time
from typing import Any
from uuid import uuid4

from app.models.schemas import Question
from app.services.ai_service import AIService

CONSENT_TTL_SECONDS = 300
MAX_PENDING_CONSENTS = 128
MAX_PENDING_CONSENT_BYTES = 32 * 1024 * 1024
MAX_CONCURRENT_PREVIEWS = 2


@dataclass(frozen=True)
class QuestionAnalysisSnapshot:
    consent_id: str
    question_id: str
    question: Question
    ai: AIService
    prompt: list[dict[str, Any]]
    fingerprint: str
    expires_at: float
    created_at: float
    size_bytes: int


class QuestionAnalysisConsentRegistry:
    """Process-local because the packaged API runs as one loopback worker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, QuestionAnalysisSnapshot] = {}
        self._active_previews = 0

    def begin_preview(self) -> bool:
        with self._lock:
            if self._active_previews >= MAX_CONCURRENT_PREVIEWS:
                return False
            self._active_previews += 1
            return True

    def end_preview(self) -> None:
        with self._lock:
            self._active_previews = max(0, self._active_previews - 1)

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
        retained_request = {
            "question_id": question.id,
            "created_at": question.created_at,
            "base_url": ai.base_url,
            "model_name": ai.model_name,
            "api_key": ai.api_key,
            "prompt": prompt,
        }
        size_bytes = len(json.dumps(retained_request, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if size_bytes > MAX_PENDING_CONSENT_BYTES:
            raise ValueError("Question analysis preview exceeds the safe memory limit")
        snapshot = QuestionAnalysisSnapshot(
            consent_id=consent_id,
            question_id=question.id,
            # The provider call needs only the question ID/timestamp after its prompt is frozen.
            question=Question(id=question.id, created_at=question.created_at),
            ai=ai,
            prompt=prompt,
            fingerprint=fingerprint,
            expires_at=now + CONSENT_TTL_SECONDS,
            created_at=now,
            size_bytes=size_bytes,
        )
        with self._lock:
            self._prune(now)
            while (
                len(self._snapshots) >= MAX_PENDING_CONSENTS
                or sum(item.size_bytes for item in self._snapshots.values()) + size_bytes > MAX_PENDING_CONSENT_BYTES
            ):
                oldest = min(self._snapshots.values(), key=lambda item: item.created_at)
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

    def discard(self, consent_id: str, question_id: str) -> None:
        with self._lock:
            snapshot = self._snapshots.get(consent_id)
            if snapshot is not None and snapshot.question_id == question_id:
                self._snapshots.pop(consent_id, None)

    def _prune(self, now: float) -> None:
        expired = [key for key, value in self._snapshots.items() if value.expires_at <= now]
        for key in expired:
            self._snapshots.pop(key, None)


question_analysis_consents = QuestionAnalysisConsentRegistry()
