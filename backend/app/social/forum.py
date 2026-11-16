"""Private, moderated study forum request and response models."""

import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class ForumPostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    body: Annotated[StrictStr, Field(min_length=1, max_length=5000)]

    @field_validator("title", "body")
    @classmethod
    def validate_text(cls, value):
        if not value.strip():
            raise ValueError("Text cannot be empty")
        try:
            value.encode("utf-8", "strict")
        except UnicodeEncodeError as exc:
            raise ValueError("Text must be valid UTF-8") from exc
        if any(unicodedata.category(char) == "Cc" and char not in "\t\n\r" for char in value):
            raise ValueError("Text contains a control character")
        return value


class ModerationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]


class ForumPost(BaseModel):
    post_id: UUID
    title: str
    body: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime


class ForumPostSummary(BaseModel):
    post_id: UUID
    status: Literal["pending", "approved", "rejected"]
