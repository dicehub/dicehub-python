from __future__ import annotations

import math
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)

from dicehub.runs.models import RunStatus

_MAX_YAML_VALUE_PATH_BYTES = 1024


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    config_id: str = Field(min_length=1, max_length=256)
    app_id: str = Field(min_length=1, max_length=256)
    config_internal_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    description: str | None
    is_default: bool
    template_version: str | None = Field(default=None, max_length=256)
    updating: bool | None


class ConfigPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    configs: tuple[Config, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class ConfigValueUpdate(BaseModel):
    """One scalar value to update in an existing YAML document."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: tuple[StrictStr, ...] = Field(min_length=1, max_length=64)
    value: StrictStr | StrictInt | StrictFloat | StrictBool | None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not 1 <= len(value) <= 64 or any(
            not segment
            or len(segment) > 255
            or any(not character.isprintable() for character in segment)
            or _not_utf8(segment)
            for segment in value
        ):
            raise ValueError("invalid YAML value path")
        try:
            path_bytes = sum(len(segment.encode("utf-8")) for segment in value) + len(value) - 1
        except UnicodeEncodeError as error:
            raise ValueError("invalid YAML value path") from error
        if path_bytes > _MAX_YAML_VALUE_PATH_BYTES:
            raise ValueError("YAML value path is too large")
        return value

    @field_validator("value")
    @classmethod
    def validate_value(
        cls, value: StrictStr | StrictInt | StrictFloat | StrictBool | None
    ) -> StrictStr | StrictInt | StrictFloat | StrictBool | None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("YAML value must be finite")
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("YAML value must be valid UTF-8") from error
        return value


def _not_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


class ConfigContentArea(str, Enum):
    TEXTS = "TEXTS"
    FILES = "FILES"


class ConfigContentType(str, Enum):
    FOLDER = "FOLDER"
    TEXT = "TEXT"
    FILE = "FILE"


class ConfigContentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(min_length=1, max_length=1024)
    resource_type: ConfigContentType


class ConfigContentPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    entries: tuple[ConfigContentEntry, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class GeometryImportRuns(BaseModel):
    """Conversion and optional first-import setup run snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    conversion_run: RunStatus
    setup_run: RunStatus | None
