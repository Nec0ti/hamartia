"""Pydantic v2 schemas for the Hamartia JSON datastore.

Every model here maps 1:1 to a record stored inside `backend/data/*.json`.
The storage service validates on load and serializes on save through these
classes, so the shape of the JSON files is enforced at the Python boundary.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Settings (backend/data/settings.json)
# ---------------------------------------------------------------------------


class Settings(BaseModel):
    """LiteLLM proxy configuration, editable through the Settings modal."""

    litellm_base_url: str = "http://localhost:4000/v1"
    model_name: str = "ollama/qwen2.5"
    api_key: str = ""


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


class CouncilAnalysis(BaseModel):
    """Full five-counselor report attached to a analyzed question."""

    dissenter: str = ""
    first_principles: str = ""
    expansionist: str = ""
    outsider: str = ""
    executor: str = ""
    verdict: CouncilVerdict = Field(default_factory=CouncilVerdict)
    analyzed_at: str = ""


class Question(BaseModel):
    id: str
    image_name: str
    image_path: str
    ocr_text: str = ""
    analysis: CouncilAnalysis | None = None
    hamartia_tag: str = "[Knowledge Gap]"
    created_at: str = ""


# ---------------------------------------------------------------------------
# Exam (backend/data/exams.json)
# ---------------------------------------------------------------------------


class Exam(BaseModel):
    """A single exam entry. Net and XP are derived, not stored."""

    id: str
    date: str = Field(description="ISO date, e.g. 2026-10-07")
    subject: str
    correct: int = Field(ge=0)
    incorrect: int = Field(ge=0)
    blank: int = Field(ge=0)
    duration_minutes: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0)
    created_at: str = ""

    # Derived metrics — excluded from serialization.
    model_config = {"populate_by_name": True}

    @property
    def total(self) -> int:
        """Total answered items (correct + incorrect)."""
        return self.correct + self.incorrect

    @property
    def net(self) -> float:
        """YKS net score: correct minus 1/4 penalty on each incorrect."""
        return self.correct - (self.incorrect / 4.0)

    @property
    def xp(self) -> int:
        """XP earned from this exam. See core/formulas.py."""
        from app.core.formulas import xp_for_exam

        return xp_for_exam(self)


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

