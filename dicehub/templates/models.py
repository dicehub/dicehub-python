from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TemplateType(str, Enum):
    APP_TEMPLATE = "APP_TEMPLATE"
    MODEL_TEMPLATE = "MODEL_TEMPLATE"


class TemplateOrderField(str, Enum):
    NAME = "name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("template timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class TemplateTag(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tag_id: str = Field(min_length=1, max_length=256)
    tag: str = Field(min_length=1, max_length=256)


class Template(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    template_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    slug: str = Field(min_length=1, max_length=256)
    description: str | None = None
    client_type: str | None = Field(default=None, max_length=256)
    route: str | None = Field(default=None, max_length=16_384)
    image_path: str | None = Field(default=None, max_length=16_384)
    icon_path: str | None = Field(default=None, max_length=16_384)
    tags: tuple[TemplateTag, ...]
    created_at: datetime | None
    updated_at: datetime | None

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc_datetime(value)


class TemplatePage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    templates: tuple[Template, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
