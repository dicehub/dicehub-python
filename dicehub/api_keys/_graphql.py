from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from dicehub._core.status import ResponseStatus
from dicehub.api_keys._validation import (
    MAX_ID_LENGTH,
    MAX_NAME_LENGTH,
    MAX_SECRET_LENGTH,
    is_valid_id,
    is_valid_name,
    is_visible_ascii,
)
from dicehub.api_keys.models import NamespacePermission

CREATE_API_KEY_MUTATION = """
mutation CreateApiKey(
  $namespaceId: String!
  $name: String!
  $permissions: [NamespacePermissionEnum]!
  $notBefore: Timestamp
  $expiresAt: Timestamp
) {
  apiKeys {
    createApiKey(
      namespaceId: $namespaceId
      name: $name
      permissions: $permissions
      notBefore: $notBefore
      expiresAt: $expiresAt
    ) {
      status {
        succeeded
        error
      }
      apiKey {
        apiKeyId
        name
        prefix
        permissions
        createdAt
        updatedAt
        lastUsedAt
        status
        notBefore
        expiresAt
        validityStatus
        value
      }
    }
  }
}
"""

LIST_API_KEYS_QUERY = """
query ListApiKeys(
  $namespaceId: String!
  $beforeApiKeyId: String
  $limit: Int!
) {
  apiKeys {
    listApiKeys(
      namespaceId: $namespaceId
      beforeApiKeyId: $beforeApiKeyId
      limit: $limit
    ) {
      status {
        succeeded
        error
      }
      apiKeys {
        apiKeyId
        name
        prefix
        permissions
        createdAt
        updatedAt
        lastUsedAt
        status
        notBefore
        expiresAt
        validityStatus
      }
    }
  }
}
"""

GET_API_KEY_QUERY = """
query GetApiKey($namespaceId: String!, $apiKeyId: String!) {
  apiKeys {
    getApiKey(namespaceId: $namespaceId, apiKeyId: $apiKeyId) {
      status {
        succeeded
        error
      }
      apiKey {
        apiKeyId
        name
        prefix
        permissions
        createdAt
        updatedAt
        lastUsedAt
        status
        notBefore
        expiresAt
        validityStatus
      }
    }
  }
}
"""

LIST_API_KEY_PERMISSIONS_QUERY = """
query ListApiKeyPermissions($namespaceId: String!) {
  apiKeys {
    listApiKeyPermissions(namespaceId: $namespaceId) {
      status {
        succeeded
        error
      }
      permissions
    }
  }
}
"""

UPDATE_API_KEY_MUTATION = """
mutation UpdateApiKey(
  $namespaceId: String!
  $apiKeyId: String!
  $name: String!
  $permissions: [NamespacePermissionEnum]
) {
  apiKeys {
    updateApiKey(
      namespaceId: $namespaceId
      apiKeyId: $apiKeyId
      name: $name
      permissions: $permissions
    ) {
      status {
        succeeded
        error
      }
      apiKey {
        apiKeyId
        name
        prefix
        permissions
        createdAt
        updatedAt
        lastUsedAt
        status
        notBefore
        expiresAt
        validityStatus
      }
    }
  }
}
"""

DELETE_API_KEY_MUTATION = """
mutation DeleteApiKey($apiKeyId: String!) {
  apiKeys {
    deleteApiKey(apiKeyId: $apiKeyId) {
      status {
        succeeded
        error
      }
    }
  }
}
"""


def _parsed_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or not value.isascii():
        raise ValueError("invalid API-key timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("invalid API-key timestamp") from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as error:
        raise ValueError("invalid API-key timestamp") from error


def _parsed_permissions(value: object) -> list[NamespacePermission]:
    if not isinstance(value, list):
        raise ValueError("invalid API-key permissions")
    parsed: list[NamespacePermission] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("invalid API-key permission")
        try:
            permission = NamespacePermission(item)
        except ValueError as error:
            raise ValueError("invalid API-key permission") from error
        if permission in parsed:
            raise ValueError("duplicate API-key permission")
        parsed.append(permission)
    return parsed


class ApiKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_key_id: str = Field(alias="apiKeyId", min_length=1, max_length=MAX_ID_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    prefix: str = Field(min_length=1, max_length=MAX_SECRET_LENGTH)
    permissions: list[NamespacePermission]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    last_used_at: datetime | None = Field(alias="lastUsedAt")
    status: Literal["ACTIVE"]
    not_before: datetime | None = Field(alias="notBefore")
    expires_at: datetime | None = Field(alias="expiresAt")
    validity_status: Literal["ACTIVE", "NOT_YET_ACTIVE", "EXPIRED"] = Field(alias="validityStatus")

    @field_validator("api_key_id")
    @classmethod
    def validate_api_key_id(cls, value: str) -> str:
        if not is_valid_id(value):
            raise ValueError("invalid API-key ID")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not is_valid_name(value):
            raise ValueError("invalid API-key name")
        return value

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not is_visible_ascii(value):
            raise ValueError("invalid API-key prefix")
        return value

    @field_validator("permissions", mode="before")
    @classmethod
    def validate_permissions(cls, value: object) -> list[NamespacePermission]:
        return _parsed_permissions(value)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_required_timestamps(cls, value: object) -> datetime:
        return _parsed_timestamp(value)

    @field_validator("last_used_at", "not_before", "expires_at", mode="before")
    @classmethod
    def validate_optional_timestamp(cls, value: object) -> datetime | None:
        return None if value is None else _parsed_timestamp(value)


class CreatedApiKeyPayload(ApiKeyPayload):
    value: SecretStr = Field(min_length=1, max_length=MAX_SECRET_LENGTH)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: SecretStr) -> SecretStr:
        if not is_visible_ascii(value.get_secret_value()):
            raise ValueError("invalid API-key value")
        return value


class CreateApiKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    api_key: CreatedApiKeyPayload | None = Field(alias="apiKey")


class CreateApiKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_api_key: CreateApiKeyPayload = Field(alias="createApiKey")


class CreateApiKeyData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: CreateApiKeys = Field(alias="apiKeys")


class ListApiKeysPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    api_keys: list[ApiKeyPayload] | None = Field(alias="apiKeys")


class ListApiKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_api_keys: ListApiKeysPayload = Field(alias="listApiKeys")


class ListApiKeysData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: ListApiKeys = Field(alias="apiKeys")


class GetApiKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    api_key: ApiKeyPayload | None = Field(alias="apiKey")


class GetApiKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_api_key: GetApiKeyPayload = Field(alias="getApiKey")


class GetApiKeyData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: GetApiKeys = Field(alias="apiKeys")


class ListApiKeyPermissionsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    permissions: list[NamespacePermission]

    @field_validator("permissions", mode="before")
    @classmethod
    def validate_permissions(cls, value: object) -> list[NamespacePermission]:
        return _parsed_permissions(value)


class ListApiKeyPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_api_key_permissions: ListApiKeyPermissionsPayload = Field(alias="listApiKeyPermissions")


class ListApiKeyPermissionsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: ListApiKeyPermissions = Field(alias="apiKeys")


class UpdateApiKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    api_key: ApiKeyPayload | None = Field(alias="apiKey")


class UpdateApiKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_api_key: UpdateApiKeyPayload = Field(alias="updateApiKey")


class UpdateApiKeyData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: UpdateApiKeys = Field(alias="apiKeys")


class DeleteApiKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class DeleteApiKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_api_key: DeleteApiKeyPayload = Field(alias="deleteApiKey")


class DeleteApiKeyData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_keys: DeleteApiKeys = Field(alias="apiKeys")
