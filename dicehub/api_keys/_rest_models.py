"""Strict REST wire representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, SecretStr

from dicehub._core.rest_models import WireModel


class ApiKeyDetail(WireModel):
    api_key_id: str
    name: str | None
    prefix: str | None
    permissions: tuple[str, ...]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    last_used_at: AwareDatetime | None
    status: Literal["ACTIVE"]
    not_before: AwareDatetime | None
    expires_at: AwareDatetime | None
    validity_status: Literal["ACTIVE", "NOT_YET_ACTIVE", "EXPIRED"]


class CreatedApiKeyDetail(WireModel):
    api_key_id: str
    name: str | None
    prefix: str | None
    permissions: tuple[str, ...]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    last_used_at: AwareDatetime | None
    status: Literal["ACTIVE"]
    not_before: AwareDatetime | None
    expires_at: AwareDatetime | None
    validity_status: Literal["ACTIVE", "NOT_YET_ACTIVE", "EXPIRED"]
    value: SecretStr


class ApiKeyList(WireModel):
    items: tuple[ApiKeyDetail, ...]


class ApiKeyPermissionList(WireModel):
    items: tuple[str, ...]


class Done(WireModel):
    succeeded: Literal[True]
