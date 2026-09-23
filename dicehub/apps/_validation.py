from __future__ import annotations

from enum import Enum
from typing import TypeVar

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError

EnumT = TypeVar("EnumT", bound=Enum)


def validated_id(value: str, label: str) -> str:
    return _shared.validated_id(value, label)


def validated_route(value: str) -> str:
    return _shared.validated_route(value, "App")


def validated_name(value: str) -> str:
    return _shared.validated_name(value, "App", min_length=3)


def validated_role_name(value: str) -> str:
    return _shared.validated_role_name(value, "App")


def validated_description(value: str | None) -> str | None:
    return _shared.validated_description(value, "App")


def validated_search_filter(value: str | None) -> str | None:
    return _shared.validated_search_filter(value, "App")


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "App")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "App")


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "App")


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    return _shared.validated_enum(value, expected_type, label)


def validated_optional_bool(value: bool | None, label: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value
