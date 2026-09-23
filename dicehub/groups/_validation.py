from __future__ import annotations

import re
from enum import Enum
from typing import BinaryIO, TypeVar

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError

MAX_GROUP_AVATAR_BYTES = 10 * 1024 * 1024
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_READ_SIZE = 64 * 1024
_SLUG_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,128}")

EnumT = TypeVar("EnumT", bound=Enum)


def validated_optional_id(value: str | None, label: str) -> str | None:
    return _shared.validated_optional_id(value, label)


def validated_id(value: str, label: str) -> str:
    return _shared.validated_id(value, label)


def validated_name(value: str) -> str:
    return _shared.validated_name(value, "Group", min_length=1)


def validated_role_name(value: str) -> str:
    return _shared.validated_role_name(value, "Group")


def validated_slug(value: str) -> str:
    if not isinstance(value, str) or _SLUG_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Group slug must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value


def validated_description(value: str | None) -> str | None:
    return _shared.validated_description(value, "Group")


def validated_route(value: str) -> str:
    return _shared.validated_route(value, "Group")


def validated_search_filter(value: str | None) -> str | None:
    return _shared.validated_search_filter(value, "Group")


def validated_enum(value: EnumT, expected_type: type[EnumT], label: str) -> EnumT:
    return _shared.validated_enum(value, expected_type, label)


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "Group")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "Group")


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "Group")


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
