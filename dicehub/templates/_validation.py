from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TypeVar

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError

_MAX_TAG_LENGTH = 256
_MAX_TAGS = 50

EnumT = TypeVar("EnumT", bound=Enum)


def validated_id(value: str) -> str:
    return _shared.validated_id(value, "Template ID", message="Template ID is invalid.")


def validated_route(value: str) -> str:
    return _shared.validated_route(value, "Template")


def validated_search_filter(value: str | None) -> str | None:
    return _shared.validated_search_filter(value, "Template")


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
    return _shared.validated_enum(value, expected_type, label)


def validated_optional_enum(
    value: EnumT | None,
    expected_type: type[EnumT],
    label: str,
) -> EnumT | None:
    return None if value is None else validated_enum(value, expected_type, label)


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "Template")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "Template")


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "Template")
