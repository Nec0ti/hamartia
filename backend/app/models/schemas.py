"""Pydantic v2 schemas for the Hamartia JSON datastore.

Every model here maps 1:1 to a record stored inside `backend/data/*.json`.
The storage service validates on load and serializes on save through these
classes, so the shape of the JSON files is enforced at the Python boundary.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, computed_field, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Settings (backend/data/settings.json)
# ---------------------------------------------------------------------------


class Settings(BaseModel):
    """LiteLLM proxy configuration, editable through the Settings modal."""

    litellm_base_url: str = "http://localhost:4000/v1"
    model_name: str = "ollama/qwen2.5"
    api_key: str = ""


class SettingsResponse(BaseModel):
    """Settings safe to send to the browser without revealing the API key."""

    litellm_base_url: str
    model_name: str
    has_api_key: bool


class SettingsUpdate(BaseModel):
    """Settings changes; a blank key preserves the saved value by default."""

    litellm_base_url: str = "http://localhost:4000/v1"
    model_name: str = "ollama/qwen2.5"
    api_key: str = ""
    clear_api_key: bool = False


# ---------------------------------------------------------------------------
# User progression (backend/data/user.json)
# ---------------------------------------------------------------------------


class RadarStats(BaseModel):
    """Four-axis performance vector rendered by the Recharts radar chart."""

    speed: int = 50
    focus: int = 50
    precision: int = 50
    stamina: int = 50


class UserStats(BaseModel):
    """Aggregate progression state. Not stored nested — serialized flat."""

    total_xp: int = 0
    level: int = 1
    streak_days: int = 1
    last_active_date: str = "2026-10-07"
    radar_stats: RadarStats = Field(default_factory=RadarStats)


# ---------------------------------------------------------------------------
# Cosmos (backend/data/cosmos.json)
# ---------------------------------------------------------------------------


class CosmosNode(BaseModel):
    """A planetary node generated from a recurring mistake tag.

    High-error subjects escalate into Boss nodes / Black Holes. `error_xp`
    is the XP wager required to assault the node; a successful assault awards
    `reward_xp`.
    """

    id: str
    name: str
    subject: str
    tag: str = "[Knowledge Gap]"
    error_count: int = 0
    error_xp: int = Field(default=100, ge=1)
    reward_xp: int = Field(default=250, ge=1)
    sector: str = "sector_0"
    is_boss: bool = False
    is_unlocked: bool = True
    # Procedural fog-of-war position on the 2D canvas.
    x: float = 0.0
    y: float = 0.0
    radius: float = 12.0


class CosmosData(BaseModel):
    nodes: list[CosmosNode] = Field(default_factory=list)
    unlocked_sectors: list[str] = Field(default_factory=lambda: ["sector_0"])
    # Read-only projection exposed by the API so the frontend can gate which
    # nodes are assaultable given the user's current XP. Not stored to disk.
    user_xp: int = 0


# ---------------------------------------------------------------------------
# Questions / Mistake Vault (backend/data/questions.json)
# ---------------------------------------------------------------------------


class CouncilVerdict(BaseModel):
    """President's synthesized, taggable diagnosis envelope."""

    hamartia_tag: str = "[Knowledge Gap]"
    root_cause: str = ""
    action_advice: str = ""
    difficulty: int = Field(ge=1, le=5)
    subject_affinity: str = ""


class CouncilMembers(BaseModel):
    dissenter: str = ""
    first_principles: str = ""
    expansionist: str = ""
    outsider: str = ""
    executor: str = ""


class CouncilAnalysis(BaseModel):
    """Council envelope; also reads records saved in the old flat shape."""

    counselors: CouncilMembers = Field(default_factory=CouncilMembers)
    verdict: CouncilVerdict = Field(default_factory=CouncilVerdict)
    analyzed_at: str = ""

    @model_validator(mode="before")
    @classmethod
    def wrap_legacy_counselors(cls, value):
        if isinstance(value, dict) and "counselors" not in value:
            keys = ("dissenter", "first_principles", "expansionist", "outsider", "executor")
            if any(key in value for key in keys):
                value = {**value, "counselors": {key: value.get(key, "") for key in keys}}
        return value


class ReviewAttempt(BaseModel):
    attempted_at: str
    correct: bool


class Question(BaseModel):
    id: str
    image_name: str = ""
    image_path: str = ""
    ocr_text: str = ""
    subject: str = ""
    topic: str = ""
    analysis: CouncilAnalysis | None = None
    hamartia_tag: str = "[Knowledge Gap]"
    created_at: str = ""
    reviewed_at: str = ""
    review_attempts: list[ReviewAttempt] = Field(default_factory=list)
    exam_id: str = ""
    question_number: int | None = Field(default=None, ge=1)
    solve_order: int | None = Field(default=None, ge=1)
    time_spent_seconds: int | None = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# Exam (backend/data/exams.json)
# ---------------------------------------------------------------------------


class ExamSection(BaseModel):
    """One subject's result inside a full TYT or AYT mock session."""

    subject: str
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    blank: int = Field(ge=0)

    @field_validator("subject")
    @classmethod
    def require_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("section subject is required")
        return value


def _exam_section_totals(exam_type, subject, correct, incorrect, blank, sections):
    if not sections:
        return subject, correct, incorrect, blank
    if exam_type == "branch":
        raise ValueError("branch exams cannot contain sections")
    names = [section.subject.casefold() for section in sections]
    if len(names) != len(set(names)):
        raise ValueError("section subjects must be unique")
    return (
        f"{exam_type.upper()} Geneli",
        sum(section.correct for section in sections),
        sum(section.incorrect for section in sections),
        sum(section.blank for section in sections),
    )


class Exam(BaseModel):
    """A single exam entry. Net and XP are derived, not stored."""

    id: str
    date: str = Field(description="ISO date, e.g. 2026-10-07")
    exam_type: Literal["tyt", "ayt", "branch"] = "branch"
    subject: str
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    blank: int = Field(ge=0)
    duration_minutes: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0)
    created_at: str = ""
    sections: list[ExamSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_section_totals(self):
        if self.sections:
            subject, correct, incorrect, blank = _exam_section_totals(
                self.exam_type, self.subject, self.correct, self.incorrect, self.blank, self.sections,
            )
            if (self.subject, self.correct, self.incorrect, self.blank) != (subject, correct, incorrect, blank):
                raise ValueError("exam totals must match section totals")
        return self

    # Derived metrics — computed on serialization via @computed_field.

    @computed_field
    @property
    def total(self) -> int:
        """Total answered items (correct + incorrect)."""
        return self.correct + self.incorrect

    @computed_field
    @property
    def net(self) -> float:
        """YKS net score: correct minus 1/4 penalty on each incorrect."""
        return self.correct - (self.incorrect / 4.0)

    @computed_field
    @property
    def xp(self) -> int:
        """XP earned from this exam. See core/formulas.py."""
        from app.core.formulas import xp_for_exam

        return xp_for_exam(self)


class ExamCreate(BaseModel):
    """Raw inputs accepted when recording an exam."""

    date: str
    exam_type: Literal["tyt", "ayt", "branch"] = "branch"
    subject: str
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    blank: int = Field(ge=0)
    duration_minutes: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0, lt=60)
    sections: list[ExamSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_section_totals(self):
        if self.sections:
            self.subject, self.correct, self.incorrect, self.blank = _exam_section_totals(
                self.exam_type, self.subject, self.correct, self.incorrect, self.blank, self.sections,
            )
        return self

    @field_validator("date")
    @classmethod
    def require_iso_date(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD") from exc
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError("date must use YYYY-MM-DD")
        return value

    @field_validator("subject")
    @classmethod
    def require_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("subject is required")
        return value


class PracticeSessionData(BaseModel):
    date: str
    subject: str
    topic: str
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    blank: int = Field(ge=0)
    duration_minutes: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0, lt=60)

    @field_validator("date")
    @classmethod
    def require_iso_date(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD") from exc
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError("date must use YYYY-MM-DD")
        return value

    @field_validator("subject", "topic")
    @classmethod
    def require_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("subject and topic are required")
        return value

    @model_validator(mode="after")
    def require_questions(self):
        if self.correct + self.incorrect + self.blank < 1:
            raise ValueError("a completed set must contain at least one question")
        return self


class PracticeSession(PracticeSessionData):
    """One completed, manually scored study set."""

    id: str
    created_at: str = ""

    @computed_field
    @property
    def net(self) -> float:
        return self.correct - self.incorrect / 4

    @computed_field
    @property
    def accuracy(self) -> float | None:
        answered = self.correct + self.incorrect
        return self.correct / answered if answered else None


class PracticeSessionCreate(PracticeSessionData):
    pass


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

