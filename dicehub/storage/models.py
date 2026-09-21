from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub.errors import ConfigurationError
from dicehub.resources._validation import validated_data_path, validated_namespace_id


class _TransferReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    namespace_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    server_verified: bool = False

    @field_validator("namespace_id")
    @classmethod
    def validate_namespace_id(cls, value: str) -> str:
        try:
            return validated_namespace_id(value)
        except ConfigurationError as error:
            raise ValueError("invalid namespace ID") from error

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        try:
            return validated_data_path(value)
        except ConfigurationError as error:
            raise ValueError("invalid storage path") from error


class UploadReceipt(_TransferReceipt):
    bytes_sent: int = Field(ge=0)


class DownloadReceipt(_TransferReceipt):
    bytes_received: int = Field(ge=0)
