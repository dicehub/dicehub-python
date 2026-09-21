from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from dicehub.errors import ConfigurationError

if TYPE_CHECKING:
    from dicehub.api_keys.models import NamespacePermission

MAX_ID_LENGTH = 256
MAX_NAME_LENGTH = 120
MAX_SECRET_LENGTH = 4096


def validated_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not is_valid_id(value):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_name(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("API-key name is invalid.")
    normalized = value.strip()
    if not is_valid_name(normalized):
        raise ConfigurationError("API-key name is invalid.")
    return normalized


def is_valid_id(value: str) -> bool:
    return (
        0 < len(value) <= MAX_ID_LENGTH
        and value.isascii()
        and value.isdigit()
        and not value.startswith("0")
    )


def is_valid_name(value: str) -> bool:
    return (
        0 < len(value) <= MAX_NAME_LENGTH
        and bool(value.strip())
        and "/" not in value
        and all(character.isprintable() for character in value)
    )


def is_visible_ascii(value: str) -> bool:
    return bool(value) and all(0x21 <= ord(character) <= 0x7E for character in value)


def validated_permissions(permissions: Sequence[NamespacePermission]) -> list[str]:
    from dicehub.api_keys.models import NamespacePermission

    if isinstance(permissions, (str, bytes)) or not permissions:
        raise ConfigurationError("At least one namespace permission is required.")

    values: list[str] = []
    for permission in permissions:
        if not isinstance(permission, NamespacePermission):
            raise ConfigurationError("Namespace permissions are invalid.")
        if permission.value in values:
            raise ConfigurationError("Namespace permissions must be unique.")
        values.append(permission.value)
    return values


def validated_validity_window(
    not_before: datetime | None,
    expires_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    normalized: list[datetime | None] = []
    for value, label in (
        (not_before, "not_before"),
        (expires_at, "expires_at"),
    ):
        if value is None:
            normalized.append(None)
            continue
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ConfigurationError(f"API-key {label} must be timezone-aware.")
        try:
            offset = value.utcoffset()
        except (OverflowError, ValueError) as error:
            raise ConfigurationError(
                f"API-key {label} is outside the supported timestamp range."
            ) from error
        if offset is None:
            raise ConfigurationError(f"API-key {label} must be timezone-aware.")
        if value.microsecond % 1000:
            raise ConfigurationError(f"API-key {label} supports millisecond precision.")
        try:
            normalized.append(value.astimezone(timezone.utc))
        except (OverflowError, ValueError) as error:
            raise ConfigurationError(
                f"API-key {label} is outside the supported timestamp range."
            ) from error

    normalized_not_before, normalized_expires_at = normalized
    if (
        normalized_not_before is not None
        and normalized_expires_at is not None
        and normalized_not_before >= normalized_expires_at
    ):
        raise ConfigurationError("API-key expires_at must be after not_before.")
    return normalized_not_before, normalized_expires_at
