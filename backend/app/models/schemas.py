"""Pydantic v2 schemas for the Hamartia JSON datastore.

Every model here maps 1:1 to a record stored inside `backend/data/*.json`.
The storage service validates on load and serializes on save through these
classes, so the shape of the JSON files is enforced at the Python boundary.
"""

from datetime import datetime
from fractions import Fraction
import ipaddress
import re
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

import idna
from pydantic import BaseModel, computed_field, Field, field_validator, model_validator

MAX_QUESTION_TEXT_BYTES = 64 * 1024


def require_utf8_byte_limit(value: str, maximum: int, field_name: str) -> str:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8 text") from exc
    if size > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-byte limit")
    return value

# ---------------------------------------------------------------------------
# Settings (backend/data/settings.json)
# ---------------------------------------------------------------------------


def _valid_http_hostname(hostname: str) -> bool:
    """Accept IP literals and UTS46 non-transitional IDNA DNS names."""
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    try:
        ascii_hostname = idna.encode(hostname, uts46=True, transitional=False, std3_rules=True).decode("ascii")
    except idna.IDNAError:
        return False
    if ascii_hostname.endswith("."):
        ascii_hostname = ascii_hostname[:-1]
    if not ascii_hostname or len(ascii_hostname) > 253:
        return False
    labels = ascii_hostname.split(".")
    for label in labels:
        if (
            len(label) > 63
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) is None
        ):
            return False
    return True


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

    @field_validator("litellm_base_url")
    @classmethod
    def bound_endpoint_url(cls, value: str) -> str:
        return require_utf8_byte_limit(value, 4096, "litellm_base_url")

    @field_validator("model_name")
    @classmethod
    def bound_model_name(cls, value: str) -> str:
        return require_utf8_byte_limit(value, 1024, "model_name")

    @field_validator("api_key")
    @classmethod
    def bound_api_key(cls, value: str) -> str:
        return require_utf8_byte_limit(value, 4096, "api_key")


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
    # Explicit user's calendar date. Older records omit it and keep their UTC-date interpretation.
    attempt_day: str = ""


class CurriculumReference(BaseModel):
    """Short curriculum notes entered by the user; Hamartia does not verify or fetch them."""

    model_config = {"extra": "forbid"}

    framework: str = Field(default="", max_length=100)
    source: str = Field(default="", max_length=160)
    version: str = Field(default="", max_length=80)
    grade_year: str = Field(default="", max_length=80)
    unit_theme: str = Field(default="", max_length=160)
    learning_outcome: str = Field(default="", max_length=500)
    process_component: str = Field(default="", max_length=200)
    source_url: str = Field(default="", max_length=2048)

    @field_validator("framework", "source", "version", "grade_year", "unit_theme", "learning_outcome", "process_component", "source_url")
    @classmethod
    def strip_reference_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_url")
    @classmethod
    def require_http_source_url(cls, value: str) -> str:
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
                and "?" not in value
                and "#" not in value
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("source_url must be an absolute HTTP(S) URL without credentials")
        return value


class Question(BaseModel):
    id: str
    image_name: str = ""
    image_path: str = ""
    ocr_text: str = ""
    subject: str = ""
    topic: str = ""
    curriculum_reference: CurriculumReference = Field(default_factory=CurriculumReference)
    analysis: CouncilAnalysis | None = None
    hamartia_tag: str = "[Knowledge Gap]"
    created_at: str = ""
    reviewed_at: str = ""
    review_attempts: list[ReviewAttempt] = Field(default_factory=list)
    exam_id: str = ""
    question_number: int | None = Field(default=None, ge=1)
    solve_order: int | None = Field(default=None, ge=1)
    time_spent_seconds: int | None = Field(default=None, ge=1)
    exam_section_total: int | None = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# Exam (backend/data/exams.json)
# ---------------------------------------------------------------------------


def _canonical_rational(value: Any) -> str:
    """Validate and canonicalize an exact integer/fraction scoring value."""
    if not isinstance(value, str) or len(value) > 32 or not value.strip():
        raise ValueError("scoring values must be exact rational strings such as 1, 0, or 1/4")
    text = value.strip()
    if re.fullmatch(r"[+-]?\d+(?:/[1-9]\d*)?", text) is None:
        raise ValueError("scoring values must be integers or fractions with a positive denominator")
    try:
        rational = Fraction(text)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("invalid rational scoring value") from exc
    if abs(rational.numerator) > 100_000 or rational.denominator > 10_000:
        raise ValueError("rational scoring value is outside supported bounds")
    return f"{rational.numerator}/{rational.denominator}"


class ExamScoringRule(BaseModel):
    """Exact additive scoring weights; wrong_penalty is subtracted."""

    correct_points: str = "1/1"
    wrong_penalty: str = "1/4"
    blank_points: str = "0/1"

    @field_validator("correct_points", "wrong_penalty", "blank_points", mode="before")
    @classmethod
    def validate_rational(cls, value: Any) -> str:
        return _canonical_rational(value)

    @model_validator(mode="after")
    def require_nonnegative_weights(self):
        if any(Fraction(getattr(self, name)) < 0 for name in ("correct_points", "wrong_penalty", "blank_points")):
            raise ValueError("correct points, wrong penalty, and blank points must be nonnegative")
        return self


class ExamScoringProfile(BaseModel):
    """Versioned user-selected policy snapshot attached to an exam."""

    profile_id: str
    version: int = Field(ge=1)
    display_name: str = Field(min_length=1, max_length=80)
    country_label: str = Field(min_length=1, max_length=80)
    scoring_rule: ExamScoringRule

    @field_validator("profile_id", "display_name", "country_label")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


def legacy_yks_profile() -> ExamScoringProfile:
    return ExamScoringProfile(
        profile_id="legacy-yks", version=1, display_name="YKS (legacy)", country_label="Türkiye",
        scoring_rule=ExamScoringRule(correct_points="1/1", wrong_penalty="1/4", blank_points="0/1"),
    )


class ExamScoringProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    country_label: str = Field(min_length=1, max_length=80)
    scoring_rule: ExamScoringRule

    @field_validator("display_name", "country_label")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


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
    # Old JSON and backups omit this field and therefore retain the legacy rule.
    scoring_profile: ExamScoringProfile = Field(default_factory=legacy_yks_profile)

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
        """Score using this record's immutable scoring-policy snapshot."""
        from app.core.formulas import net_for_scoring_rule

        return net_for_scoring_rule(self.correct, self.incorrect, self.blank, self.scoring_profile.scoring_rule)

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
    scoring_profile_id: str | None = None
    scoring_profile_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_scoring_profile_reference(self):
        if (self.scoring_profile_id is None) != (self.scoring_profile_version is None):
            raise ValueError("scoring profile ID and version must be provided together")
        if self.scoring_profile_id is not None and not self.scoring_profile_id.strip():
            raise ValueError("scoring profile ID is required")
        return self

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
    # Old records remain immutable legacy snapshots when the field is absent.
    scoring_profile: ExamScoringProfile = Field(default_factory=legacy_yks_profile)

    @computed_field
    @property
    def net(self) -> float:
        from app.core.formulas import net_for_scoring_rule

        return net_for_scoring_rule(self.correct, self.incorrect, self.blank, self.scoring_profile.scoring_rule)

    @computed_field
    @property
    def accuracy(self) -> float | None:
        answered = self.correct + self.incorrect
        return self.correct / answered if answered else None


class PracticeSessionCreate(PracticeSessionData):
    scoring_profile_id: str | None = None
    scoring_profile_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_scoring_profile_reference(self):
        if (self.scoring_profile_id is None) != (self.scoring_profile_version is None):
            raise ValueError("scoring profile ID and version must be provided together")
        if self.scoring_profile_id is not None and not self.scoring_profile_id.strip():
            raise ValueError("scoring profile ID is required")
        return self


class PracticeDraftCompletion(PracticeSessionData):
    """Immutable request and profile snapshot frozen before focused completion POST."""

    scoring_profile_id: str = Field(min_length=1)
    scoring_profile_version: int = Field(ge=1)
    scoring_profile: ExamScoringProfile

    @model_validator(mode="after")
    def validate_profile_snapshot_reference(self):
        if (self.scoring_profile_id, self.scoring_profile_version) != (
            self.scoring_profile.profile_id, self.scoring_profile.version,
        ):
            raise ValueError("completion payload profile reference must match its snapshot")
        return self


class LearningEvidenceData(BaseModel):
    """A user's reflection on an activity completed from a suggested topic."""

    model_config = {"extra": "forbid"}

    date: str
    subject: str = Field(min_length=1, max_length=120)
    topic: str = Field(min_length=1, max_length=160)
    activity: str = Field(min_length=1, max_length=500)
    observation: str = Field(min_length=1, max_length=3000)
    reference_url: str = Field(default="", max_length=2048)

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

    @field_validator("subject", "topic", "activity", "observation", "reference_url")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("subject", "topic", "activity", "observation")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("reference_url")
    @classmethod
    def require_http_reference(cls, value: str) -> str:
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            _ = parsed.port
            valid = (
                parsed.scheme in {"http", "https"}
                and _valid_http_hostname(parsed.hostname or "")
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("reference_url must be an absolute HTTP(S) URL without credentials")
        return value


class LearningEvidence(LearningEvidenceData):
    id: str
    created_at: str = ""


class LearningEvidenceCreate(LearningEvidenceData):
    pass


class LearningEvidenceDeletedApprovalLedger(BaseModel):
    """Content-free approval IDs retained so deleted AI entries cannot replay."""

    model_config = {"extra": "forbid"}

    approval_ids: list[UUID] = Field(default_factory=list)


class QuestionDeletedApprovalLedger(BaseModel):
    """Content-free approval IDs retained to prevent replay after deleting an agent-created question."""

    model_config = {"extra": "forbid"}

    approval_ids: list[UUID] = Field(default_factory=list)


class ExamDeletedApprovalLedger(BaseModel):
    """Content-free Study Agent approval IDs retained after deleting captured exams."""

    model_config = {"extra": "forbid"}

    approval_ids: list[UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Clock and active study timer (backend/data/clock.json)
# ---------------------------------------------------------------------------


class ClockPreferences(BaseModel):
    pomodoro_work_minutes: int = Field(default=25, ge=1, le=180)
    pomodoro_break_minutes: int = Field(default=5, ge=1, le=60)
    pomodoro_cycle: bool = False
    notifications_opt_in: bool = False


class ClockAlarm(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    kind: Literal["once", "weekdays"]
    one_off_at_ms: int | None = Field(default=None, ge=0)
    local_time: str = ""
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    enabled: bool = True
    next_at_ms: int | None = Field(default=None, ge=0)
    overdue_at_ms: int | None = Field(default=None, ge=0)
    last_fired_at_ms: int | None = Field(default=None, ge=0)

    @field_validator("label")
    @classmethod
    def normalize_alarm_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("alarm label is required")
        return value

    @field_validator("local_time")
    @classmethod
    def validate_local_time(cls, value: str) -> str:
        if value and (len(value) != 5 or value[2] != ":" or not value[:2].isdigit() or not value[3:].isdigit()):
            raise ValueError("local_time must use HH:MM")
        if value and (int(value[:2]) > 23 or int(value[3:]) > 59):
            raise ValueError("local_time must use a valid 24-hour time")
        return value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value) or len(set(value)) != len(value):
            raise ValueError("weekdays must be unique values from 0 to 6")
        return value

    @model_validator(mode="after")
    def validate_alarm_schedule(self):
        if self.kind == "once":
            if self.one_off_at_ms is None or self.local_time or self.weekdays:
                raise ValueError("one-off alarms require a timestamp and no weekday schedule")
            if self.next_at_ms is not None and self.next_at_ms != self.one_off_at_ms:
                raise ValueError("one-off next occurrence must match its timestamp")
        elif self.one_off_at_ms is not None or not self.local_time or not self.weekdays:
            raise ValueError("weekday alarms require a local time and at least one weekday")
        if self.enabled and self.next_at_ms is None:
            raise ValueError("enabled alarms require their next occurrence")
        return self


class PracticeDraft(BaseModel):
    date: str
    subject: str = Field(min_length=1, max_length=120)
    topic: str = Field(min_length=1, max_length=120)
    correct: int = Field(default=0, ge=0)
    incorrect: int = Field(default=0, ge=0)
    blank: int = Field(default=0, ge=0)
    completion_id: str | None = Field(default=None, min_length=36, max_length=36)
    scoring_profile: ExamScoringProfile = Field(default_factory=legacy_yks_profile)
    completion_payload: PracticeDraftCompletion | None = None

    @field_validator("completion_id")
    @classmethod
    def validate_completion_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(UUID(value))
        except (ValueError, AttributeError) as exc:
            raise ValueError("completion_id must be a UUID") from exc

    @field_validator("date")
    @classmethod
    def validate_draft_date(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD") from exc
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError("date must use YYYY-MM-DD")
        return value

    @field_validator("subject", "topic")
    @classmethod
    def normalize_draft_labels(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("subject and topic are required")
        return value

    @model_validator(mode="after")
    def validate_frozen_completion(self):
        payload = self.completion_payload
        if payload is None:
            return self
        if self.completion_id is None:
            raise ValueError("a frozen completion payload requires an idempotency key")
        if (self.date, self.subject, self.topic, self.correct, self.incorrect, self.blank) != (
            payload.date, payload.subject, payload.topic, payload.correct, payload.incorrect, payload.blank,
        ):
            raise ValueError("a frozen completion payload must match its practice draft")
        if payload.scoring_profile != self.scoring_profile:
            raise ValueError("a frozen completion payload must preserve the selected profile snapshot")
        return self


class ClockLap(BaseModel):
    elapsed_ms: int = Field(ge=0, le=31_536_000_000)
    recorded_at_ms: int = Field(ge=0)


class ActiveClockTimer(BaseModel):
    kind: Literal["practice", "pomodoro", "countdown", "stopwatch"]
    status: Literal["running", "paused", "overdue"]
    elapsed_ms: int = Field(default=0, ge=0, le=31_536_000_000)
    started_at_ms: int | None = Field(default=None, ge=0)
    deadline_at_ms: int | None = Field(default=None, ge=0)
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)
    remaining_ms: int = Field(default=0, ge=0, le=86_400_000)
    work_duration_ms: int = Field(default=0, ge=0, le=10_800_000)
    break_duration_ms: int = Field(default=0, ge=0, le=3_600_000)
    phase: Literal["work", "break"] | None = None
    cycle_enabled: bool = False
    cycle_count: int = Field(default=0, ge=0, le=1_000_000)
    overdue_at_ms: int | None = Field(default=None, ge=0)
    laps: list[ClockLap] = Field(default_factory=list, max_length=100)
    practice_draft: PracticeDraft | None = None

    @model_validator(mode="after")
    def validate_active_timer(self):
        if (self.kind == "practice") != (self.practice_draft is not None):
            raise ValueError("only practice timers carry a practice draft")
        if self.practice_draft and self.practice_draft.completion_payload and self.status != "paused":
            raise ValueError("a focused timer with a frozen completion payload must remain paused")
        if self.kind == "pomodoro":
            if (self.phase is None or self.duration_ms < 1_000 or self.work_duration_ms < 1_000
                    or self.break_duration_ms < 1_000):
                raise ValueError("Pomodoro timers require a phase and both phase durations")
        elif self.phase is not None or self.cycle_enabled or self.cycle_count or self.work_duration_ms or self.break_duration_ms:
            raise ValueError("Pomodoro fields are only valid for Pomodoro timers")
        if self.kind == "countdown" and self.duration_ms < 1_000:
            raise ValueError("countdown timers require a duration")
        if self.kind in ("practice", "stopwatch") and (self.duration_ms or self.remaining_ms or self.deadline_at_ms):
            raise ValueError("stopwatch timers do not use a countdown deadline")
        if self.kind in ("countdown", "pomodoro"):
            if self.elapsed_ms or self.started_at_ms or self.laps:
                raise ValueError("countdown timers do not use stopwatch state")
        if self.status == "running":
            if self.kind in ("countdown", "pomodoro") and self.deadline_at_ms is None:
                raise ValueError("running countdown timers require a deadline")
            if self.kind in ("practice", "stopwatch") and self.started_at_ms is None:
                raise ValueError("running stopwatch timers require a start timestamp")
            if self.overdue_at_ms is not None:
                raise ValueError("running timers cannot be overdue")
        elif self.started_at_ms is not None or self.deadline_at_ms is not None:
            raise ValueError("paused and overdue timers cannot keep a running timestamp")
        if self.status == "overdue":
            if self.kind not in ("countdown", "pomodoro") or self.overdue_at_ms is None or self.remaining_ms:
                raise ValueError("only expired countdown timers can be overdue")
        elif self.overdue_at_ms is not None:
            raise ValueError("only overdue timers can have an overdue timestamp")
        return self


class ClockState(BaseModel):
    preferences: ClockPreferences = Field(default_factory=ClockPreferences)
    alarms: list[ClockAlarm] = Field(default_factory=list, max_length=128)
    active_timer: ActiveClockTimer | None = None

    @model_validator(mode="after")
    def require_unique_alarm_ids(self):
        identifiers = [alarm.id for alarm in self.alarms]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("clock alarm IDs must be unique")
        return self


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

