from __future__ import annotations

import math
import re
from collections.abc import Sequence
from enum import Enum
from typing import TypeVar
from uuid import UUID

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError

_MAX_GRAPHQL_INT = 2**31 - 1
_MACHINE_TYPE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}")
MAX_RESULT_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_RUN_WAIT_SECONDS = 7 * 24 * 60 * 60
MIN_RUN_POLL_SECONDS = 0.1

EnumT = TypeVar("EnumT", bound=Enum)


def validated_id(value: str, label: str) -> str:
    return _shared.validated_id(value, label)


def validated_optional_id(value: str | None, label: str) -> str | None:
    return _shared.validated_optional_id(value, label)


def validated_uuid(value: str, label: str) -> str:
    parsed: UUID | None = None
    if isinstance(value, str) and len(value) == 36 and value.isascii():
        try:
            parsed = UUID(value)
        except ValueError:
            pass
    if parsed is None or str(parsed) != value.lower():
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return str(parsed)


def validated_wait_settings(
    timeout_seconds: float,
    poll_seconds: float,
) -> tuple[float, float]:
    valid_timeout = _validated_seconds(timeout_seconds, "Run timeout")
    valid_poll = _validated_seconds(poll_seconds, "Run polling interval")
    if valid_timeout > MAX_RUN_WAIT_SECONDS:
        raise ConfigurationError("Run timeout must not exceed 7 days.")
    if valid_poll < MIN_RUN_POLL_SECONDS:
        raise ConfigurationError("Run polling interval must be at least 0.1 seconds.")
    if valid_poll > valid_timeout:
        raise ConfigurationError("Run polling interval must not exceed the run timeout.")
    return valid_timeout, valid_poll


def _validated_seconds(value: float, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ConfigurationError(f"{label} must be a positive finite number of seconds.")
    return float(value)


def validated_result_archive_limit(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_RESULT_ARCHIVE_BYTES
    ):
        raise ConfigurationError("Run result archive limit must be between 1 byte and 2 GiB.")
    return value


def validated_bool(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_machine_type_id(value: str) -> str:
    if not isinstance(value, str) or _MACHINE_TYPE_PATTERN.fullmatch(value) is None:
        raise ConfigurationError("Machine type ID is invalid.")
    return value


def validated_positive_count(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_GRAPHQL_INT:
        raise ConfigurationError(f"{label.capitalize()} must be a positive GraphQL integer.")
    return value


def validated_optional_positive_count(value: int | None, label: str) -> int | None:
    return None if value is None else validated_positive_count(value, label)


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    return _shared.validated_enum(value, expected_type, label)


def validated_enum_values(
    values: Sequence[EnumT] | None,
    expected_type: type[EnumT],
    label: str,
) -> list[str] | None:
    if values is None:
        return None
    if isinstance(values, str | bytes) or not isinstance(values, Sequence) or not values:
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    result: list[str] = []
    for value in values:
        if not isinstance(value, expected_type) or not isinstance(value.value, str):
            raise ConfigurationError(f"{label.capitalize()} is invalid.")
        if value.value in result:
            raise ConfigurationError(f"{label.capitalize()} must not contain duplicates.")
        result.append(value.value)
    return result


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "Run")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "Run", graphql_int=True)


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "Run")
