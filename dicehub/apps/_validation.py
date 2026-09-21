from __future__ import annotations

from enum import Enum
from typing import TypeVar

from dicehub.errors import ConfigurationError

_MAX_ID_LENGTH = 256
_MAX_FILTER_LENGTH = 256
_MAX_CURSOR_LENGTH = 16_384
_MAX_ROUTE_LENGTH = 16_384
_MAX_PAGE_SIZE = 50
_MAX_SAFE_FLOAT_INTEGER = 2**53 - 1
_MIN_NAME_LENGTH = 3
_MAX_NAME_LENGTH = 128

EnumT = TypeVar("EnumT", bound=Enum)


def validated_id(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith("0")
        or len(value) > _MAX_ID_LENGTH
    ):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_route(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > _MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("App route is invalid.")
    return value


def validated_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _MIN_NAME_LENGTH <= len(value) <= _MAX_NAME_LENGTH
        or not value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(
            f"App name must be {_MIN_NAME_LENGTH} to {_MAX_NAME_LENGTH} printable characters."
        )
    return value


def validated_role_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= _MAX_NAME_LENGTH
        or value != value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("App role name must be 1 to 128 printable characters.")
    return value


def validated_description(value: str | None) -> str | None:
    if value is not None and (not isinstance(value, str) or "\0" in value):
        raise ConfigurationError("App description is invalid.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("App search filter is invalid.")
    return value


def validated_page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ConfigurationError(f"App page size must be between 1 and {_MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_SAFE_FLOAT_INTEGER
    ):
        raise ConfigurationError("App offset must be a non-negative safe integer.")
    return value


def validated_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CURSOR_LENGTH
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ConfigurationError("App cursor is invalid.")
    return value


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    if not isinstance(value, expected_type):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_optional_bool(value: bool | None, label: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value
