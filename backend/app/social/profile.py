"""Private profile fields and a pure allowlisted public projection."""

import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator


AvatarPreset = Literal["sunrise", "moon", "leaf", "star", "book", "mountain", "wave", "lantern"]
ShortText = Annotated[StrictStr, Field(max_length=80)]
MediumText = Annotated[StrictStr, Field(max_length=120)]
LongText = Annotated[StrictStr, Field(max_length=2000)]


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: ShortText | None = None
    age: Annotated[StrictInt, Field(ge=5, le=120)] | None = None
    school_grade: ShortText | None = None
    school_class: ShortText | None = None
    curriculum: MediumText | None = None
    study_preferences: LongText | None = None
    study_goals: LongText | None = None
    avatar_preset: AvatarPreset | None = None
    nickname_public: StrictBool = False
    age_public: StrictBool = False
    school_grade_public: StrictBool = False
    school_class_public: StrictBool = False
    curriculum_public: StrictBool = False
    study_preferences_public: StrictBool = False
    study_goals_public: StrictBool = False
    avatar_preset_public: StrictBool = False

    @field_validator("nickname", "school_grade", "school_class", "curriculum", "study_preferences", "study_goals")
    @classmethod
    def validate_safe_text(cls, value):
        if value is None:
            return value
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise ValueError("Text must be valid UTF-8") from exc
        if any(unicodedata.category(char) == "Cc" and char not in "\t\n\r" for char in value):
            raise ValueError("Text contains a control character")
        return value


class Profile(BaseModel):
    nickname: str | None = None
    age: int | None = None
    school_grade: str | None = None
    school_class: str | None = None
    curriculum: str | None = None
    study_preferences: str | None = None
    study_goals: str | None = None
    avatar_preset: AvatarPreset | None = None
    nickname_public: bool = False
    age_public: bool = False
    school_grade_public: bool = False
    school_class_public: bool = False
    curriculum_public: bool = False
    study_preferences_public: bool = False
    study_goals_public: bool = False
    avatar_preset_public: bool = False


_PUBLIC_FIELD_FLAGS = (
    ("nickname", "nickname_public"),
    ("age", "age_public"),
    ("school_grade", "school_grade_public"),
    ("school_class", "school_class_public"),
    ("curriculum", "curriculum_public"),
    ("study_preferences", "study_preferences_public"),
    ("study_goals", "study_goals_public"),
    ("avatar_preset", "avatar_preset_public"),
)


def public_profile_projection(profile: Profile | dict) -> dict:
    """Project only explicitly visible, allowlisted profile values."""
    values = profile.model_dump() if isinstance(profile, Profile) else profile
    return {
        field: values[field]
        for field, flag in _PUBLIC_FIELD_FLAGS
        if values.get(flag) is True and values.get(field) is not None
    }
