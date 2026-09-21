from __future__ import annotations

import re
from typing import TypeVar

from dicehub._core.membership import MembershipVisibility
from dicehub.errors import ConfigurationError
from dicehub.projects.models import ProjectOrderField, ProjectVisibility, SortOrder

_MAX_ID_LENGTH = 256
_MAX_FILTER_LENGTH = 256
_MAX_CURSOR_LENGTH = 16_384
_MAX_ROUTE_LENGTH = 16_384
_MAX_PAGE_SIZE = 50
_MAX_SAFE_FLOAT_INTEGER = 2**53 - 1
_MIN_NAME_LENGTH = 3
_MAX_NAME_LENGTH = 128
_SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,128}")

EnumT = TypeVar(
    "EnumT",
    ProjectOrderField,
    ProjectVisibility,
    SortOrder,
    MembershipVisibility,
)


def validated_optional_id(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith("0")
        or len(value) > _MAX_ID_LENGTH
    ):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_id(value: str, label: str) -> str:
    validated = validated_optional_id(value, label)
    if validated is None:
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return validated


def validated_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _MIN_NAME_LENGTH <= len(value) <= _MAX_NAME_LENGTH
        or not value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(
            f"Project name must be {_MIN_NAME_LENGTH} to {_MAX_NAME_LENGTH} printable characters."
        )
    return value


def validated_role_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= _MAX_NAME_LENGTH
        or value != value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Project role name must be 1 to 128 printable characters.")
    return value


def validated_slug(value: str) -> str:
    if not isinstance(value, str) or _SLUG_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Project slug must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value


def validated_route(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > _MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Project route is invalid.")
    return value


def validated_description(value: str | None) -> str | None:
    if value is not None and (not isinstance(value, str) or "\0" in value):
        raise ConfigurationError("Project description is invalid.")
    return value


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    if not isinstance(value, expected_type):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Project search filter is invalid.")
    return value


def validated_page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ConfigurationError(f"Project page size must be between 1 and {_MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_SAFE_FLOAT_INTEGER
    ):
        raise ConfigurationError("Project offset must be a non-negative safe integer.")
    return value


def validated_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CURSOR_LENGTH
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ConfigurationError("Project cursor is invalid.")
    return value
