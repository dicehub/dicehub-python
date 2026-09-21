from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence

from dicehub.configs.models import ConfigValueUpdate
from dicehub.errors import ConfigurationError

_MAX_ID_LENGTH = 256
_MAX_FILTER_LENGTH = 256
_MAX_CURSOR_LENGTH = 16_384
_MAX_PAGE_SIZE = 50
_MAX_SAFE_FLOAT_INTEGER = 2**53 - 1
_MAX_NAME_LENGTH = 128
_MAX_CONTENT_PATH_LENGTH = 1024
_MAX_CONTENT_SEGMENT_LENGTH = 255
_MAX_YAML_VALUE_PATH_BYTES = 1024
_MAX_TEXT_BYTES = 2 * 1024 * 1024
_MAX_CONFIG_VALUE_UPDATES = 100
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
_GEOMETRY_FILENAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*\.stl")


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


def validated_name(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= _MAX_NAME_LENGTH
        or not value.strip()
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError(
            f"Config name must be 1 to {_MAX_NAME_LENGTH} printable characters."
        )
    return value


def validated_description(value: str | None) -> str | None:
    if value is not None and (not isinstance(value, str) or "\0" in value):
        raise ConfigurationError("Config description is invalid.")
    return value


def validated_content_path(value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Config content path is invalid.")
    if value == "" and allow_empty:
        return value
    if (
        not value
        or len(value) > _MAX_CONTENT_PATH_LENGTH
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Config content path is invalid.")
    if any(
        not part or part in {".", ".."} or len(part) > _MAX_CONTENT_SEGMENT_LENGTH
        for part in value.split("/")
    ):
        raise ConfigurationError("Config content path is invalid.")
    return value


def validated_yaml_path(value: str) -> str:
    path = validated_content_path(value)
    if not path.lower().endswith(".yaml"):
        raise ConfigurationError("Config value path must name an existing .yaml resource.")
    return path


def validated_yaml_value_path(value: tuple[str, ...]) -> tuple[str, ...]:
    if (
        not isinstance(value, tuple)
        or not 1 <= len(value) <= 64
        or any(
            not isinstance(segment, str)
            or not segment
            or len(segment) > _MAX_CONTENT_SEGMENT_LENGTH
            or any(not character.isprintable() for character in segment)
            or _not_utf8(segment)
            for segment in value
        )
    ):
        raise ConfigurationError("Config YAML value path is invalid.")
    try:
        path_bytes = sum(len(segment.encode("utf-8")) for segment in value) + len(value) - 1
    except UnicodeEncodeError as error:
        raise ConfigurationError("Config YAML value path is invalid.") from error
    if path_bytes > _MAX_YAML_VALUE_PATH_BYTES:
        raise ConfigurationError("Config YAML value path is too large.")
    return value


def validated_config_value_updates(
    values: Sequence[ConfigValueUpdate],
) -> list[dict[str, object]]:
    if (
        isinstance(values, str | bytes)
        or not isinstance(values, Sequence)
        or not 1 <= len(values) <= _MAX_CONFIG_VALUE_UPDATES
    ):
        raise ConfigurationError("Config value updates must contain between 1 and 100 updates.")

    updates: list[dict[str, object]] = []
    paths: set[tuple[str, ...]] = set()
    text_bytes = 0
    for update in values:
        if not isinstance(update, ConfigValueUpdate):
            raise ConfigurationError("Config value updates must use ConfigValueUpdate models.")
        path = validated_yaml_value_path(update.path)
        if path in paths:
            raise ConfigurationError("Config value update paths must be unique.")
        paths.add(path)

        value = update.value
        if type(value) not in {str, int, float, bool, type(None)}:
            raise ConfigurationError("Config value updates must contain scalar values.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ConfigurationError("Config value updates must contain finite floats.")
        if isinstance(value, str):
            try:
                text_bytes += len(value.encode("utf-8"))
            except UnicodeEncodeError as error:
                raise ConfigurationError("Config value strings must be valid UTF-8.") from error
            if text_bytes > _MAX_TEXT_BYTES:
                raise ConfigurationError("Config value strings must not exceed 2 MiB in total.")
        updates.append({"path": list(path), "value": value})

    try:
        encoded_updates = json.dumps(
            updates,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as error:
        raise ConfigurationError("Config value updates are not JSON encodable.") from error
    if len(encoded_updates) > _MAX_TEXT_BYTES:
        raise ConfigurationError("Config value updates must not exceed 2 MiB.")
    return updates


def _not_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def validated_geometry_filename(value: str) -> str:
    """Validate one existing STL basename accepted by the fixed import operation."""

    if (
        not isinstance(value, str)
        or not value.isascii()
        or not 1 <= len(value) <= _MAX_CONTENT_SEGMENT_LENGTH
        or _GEOMETRY_FILENAME.fullmatch(value) is None
    ):
        raise ConfigurationError("Geometry filename must be one STL basename.")
    return value


def validated_text_content(value: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Config text must not exceed 2 MiB.")
    encoded: bytes | None = None
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        pass
    if encoded is None or len(encoded) > _MAX_TEXT_BYTES:
        raise ConfigurationError("Config text must be valid UTF-8 and not exceed 2 MiB.")
    return value.replace("\r\n", "\n")


def validated_file_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_FILE_BYTES:
        raise ConfigurationError("Config file limit must be between 1 byte and 2 GiB.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_FILTER_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Config search filter is invalid.")
    return value


def validated_page_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_PAGE_SIZE:
        raise ConfigurationError(f"Config page size must be between 1 and {_MAX_PAGE_SIZE}.")
    return value


def validated_offset(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_SAFE_FLOAT_INTEGER
    ):
        raise ConfigurationError("Config offset must be a non-negative safe integer.")
    return value


def validated_cursor(value: str | None) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > _MAX_CURSOR_LENGTH
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ConfigurationError("Config cursor is invalid.")
    return value
