from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TypeVar

from dicehub.errors import ConfigurationError

_MAX_ID_LENGTH = 256
_MAX_FILTER_LENGTH = 256
_MAX_TAG_LENGTH = 256
_MAX_TAGS = 50
_MAX_CURSOR_LENGTH = 16_384
_MAX_ROUTE_LENGTH = 16_384
_MAX_PAGE_SIZE = 50
_MAX_SAFE_FLOAT_INTEGER = 2**53 - 1

EnumT = TypeVar("EnumT", bound=Enum)


def validated_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith("0")
        or len(value) > _MAX_ID_LENGTH
    ):
        raise ConfigurationError("Template ID is invalid.")
    return value


def validated_route(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > _MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Template route is invalid.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Template search filter is invalid.")
    return value


def validated_tags(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or not values
        or len(values) > _MAX_TAGS
    ):
        raise ConfigurationError("Template tags are invalid.")

    result: list[str] = []
    for value in values:
        if (
            not isinstance(value, str)
            or not 1 <= len(value) <= _MAX_TAG_LENGTH
            or any(not character.isprintable() for character in value)
        ):
            raise ConfigurationError("Template tags are invalid.")
        if value in result:
            raise ConfigurationError("Template tags must not contain duplicates.")
        result.append(value)
    return result


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    if not isinstance(value, expected_type):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_optional_enum(
    value: EnumT | None,
    expected_type: type[EnumT],
    label: str,
) -> EnumT | None:
    return None if value is None else validated_enum(value, expected_type, label)


def validated_page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ConfigurationError(f"Template page size must be between 1 and {_MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_SAFE_FLOAT_INTEGER
    ):
        raise ConfigurationError("Template offset must be a non-negative safe integer.")
    return value


def validated_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CURSOR_LENGTH
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ConfigurationError("Template cursor is invalid.")
    return value
