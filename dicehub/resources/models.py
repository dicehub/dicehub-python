from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub.errors import ConfigurationError, ProtocolError
from dicehub.resources._validation import (
    validated_namespace_id,
    validated_resource_id,
    validated_server_data_key,
)


class ResourceType(str, Enum):
    FOLDER = "FOLDER"
    TEXT = "TEXT"
    FILE = "FILE"
    CHANNEL = "CHANNEL"


class Resource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_id: str
    namespace_id: str
    key: str = Field(min_length=4, max_length=1029)
    resource_type: ResourceType

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        try:
            return validated_resource_id(value)
        except ConfigurationError as error:
            raise ValueError("invalid resource ID") from error

    @field_validator("namespace_id")
    @classmethod
    def validate_namespace_id(cls, value: str) -> str:
        try:
            return validated_namespace_id(value)
        except ConfigurationError as error:
            raise ValueError("invalid namespace ID") from error

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        try:
            return validated_server_data_key(value)
        except ProtocolError as error:
            raise ValueError("invalid resource key") from error


class ResourcePage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resources: tuple[Resource, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
