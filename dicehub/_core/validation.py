"""Shared input validation for domain services."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from dicehub.errors import ConfigurationError

MAX_ID_LENGTH = 256
MAX_FILTER_LENGTH = 256
MAX_CURSOR_LENGTH = 16_384
MAX_ROUTE_LENGTH = 16_384
MAX_PAGE_SIZE = 50
MAX_SAFE_FLOAT_INTEGER = 2**53 - 1
MAX_GRAPHQL_INT = 2**31 - 1

EnumT = TypeVar("EnumT", bound=Enum)


def is_valid_id(value: str) -> bool:
    return (
        0 < len(value) <= MAX_ID_LENGTH
        and value.isascii()
        and value.isdigit()
        and not value.startswith("0")
    )


def validated_id(value: str, label: str, *, message: str | None = None) -> str:
    if not isinstance(value, str) or not is_valid_id(value):
        raise ConfigurationError(message or f"{label.capitalize()} is invalid.")
    return value


def validated_optional_id(value: str | None, label: str) -> str | None:
    return None if value is None else validated_id(value, label)


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    if not isinstance(value, expected_type):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_route(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(f"{label} route is invalid.")
    return value


def validated_name(value: str, label: str, *, min_length: int, max_length: int = 128) -> str:
    if (
        not isinstance(value, str)
        or not min_length <= len(value) <= max_length
        or not value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(
            f"{label} name must be {min_length} to {max_length} printable characters."
        )
    return value


def validated_role_name(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or value != value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(f"{label} role name must be 1 to 128 printable characters.")
    return value


def validated_description(value: str | None, label: str) -> str | None:
    if value is not None and (not isinstance(value, str) or "\0" in value):
        raise ConfigurationError(f"{label} description is invalid.")
    return value


def validated_search_filter(value: str | None, label: str) -> str | None:
    if value is not None and (
        not isinstance(value, str)
        or len(value) > MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(f"{label} search filter is invalid.")
    return value


def validated_page_size(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_PAGE_SIZE:
        raise ConfigurationError(f"{label} page size must be between 1 and {MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int, label: str, *, graphql_int: bool = False) -> int:
    maximum = MAX_GRAPHQL_INT if graphql_int else MAX_SAFE_FLOAT_INTEGER
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        kind = "GraphQL integer" if graphql_int else "safe integer"
        raise ConfigurationError(f"{label} offset must be a non-negative {kind}.")
    return value


def validated_cursor(value: str | None, label: str, *, printable: bool = False) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > MAX_CURSOR_LENGTH
        or (printable and not value)
        or any(
            not character.isprintable() if printable else not 0x21 <= ord(character) <= 0x7E
            for character in value
        )
    ):
        raise ConfigurationError(f"{label} cursor is invalid.")
    return value
