from __future__ import annotations

import re
from enum import Enum
from typing import BinaryIO, TypeVar

from dicehub.errors import ConfigurationError

_MAX_ID_LENGTH = 256
_MAX_FILTER_LENGTH = 256
_MAX_CURSOR_LENGTH = 16_384
_MAX_ROUTE_LENGTH = 16_384
_MAX_PAGE_SIZE = 50
_MAX_SAFE_FLOAT_INTEGER = 2**53 - 1
MAX_GROUP_AVATAR_BYTES = 10 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_READ_SIZE = 64 * 1024
_MIN_NAME_LENGTH = 1
_MAX_NAME_LENGTH = 128
_SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,128}")

EnumT = TypeVar("EnumT", bound=Enum)


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
    result = validated_optional_id(value, label)
    if result is None:
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return result


def validated_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _MIN_NAME_LENGTH <= len(value) <= _MAX_NAME_LENGTH
        or not value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(
            f"Group name must be {_MIN_NAME_LENGTH} to {_MAX_NAME_LENGTH} printable characters."
        )
    return value


def validated_role_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= _MAX_NAME_LENGTH
        or value != value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Group role name must be 1 to 128 printable characters.")
    return value


def validated_slug(value: str) -> str:
    if not isinstance(value, str) or _SLUG_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Group slug must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value


def validated_description(value: str | None) -> str | None:
    if value is not None and (not isinstance(value, str) or "\0" in value):
        raise ConfigurationError("Group description is invalid.")
    return value


def validated_route(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > _MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Group route is invalid.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Group search filter is invalid.")
    return value


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    if not isinstance(value, expected_type):
        raise ConfigurationError(f"{label.capitalize()} is invalid.")
    return value


def validated_page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ConfigurationError(f"Group page size must be between 1 and {_MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_SAFE_FLOAT_INTEGER
    ):
        raise ConfigurationError("Group offset must be a non-negative safe integer.")
    return value


def validated_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CURSOR_LENGTH
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ConfigurationError("Group cursor is invalid.")
    return value


def validated_avatar_png(source: BinaryIO) -> bytes:
    read = getattr(source, "read", None)
    if not callable(read):
        raise ConfigurationError("Group avatar source must be readable.")

    content = bytearray()
    read_failed = False
    try:
        while len(content) <= MAX_GROUP_AVATAR_BYTES:
            chunk = read(min(_READ_SIZE, MAX_GROUP_AVATAR_BYTES + 1 - len(content)))
            if not isinstance(chunk, bytes | bytearray | memoryview):
                raise ConfigurationError("Group avatar source must provide binary data.")
            if not chunk:
                break
            if len(chunk) > MAX_GROUP_AVATAR_BYTES - len(content):
                raise ConfigurationError("Group avatar must not exceed 10 MiB.")
            content.extend(chunk)
    except OSError:
        read_failed = True

    if read_failed:
        raise ConfigurationError("Group avatar source could not be read.")

    if len(content) > MAX_GROUP_AVATAR_BYTES:
        raise ConfigurationError("Group avatar must not exceed 10 MiB.")
    if not content.startswith(_PNG_SIGNATURE):
        raise ConfigurationError("Group avatar must be a PNG image.")
    return bytes(content)
