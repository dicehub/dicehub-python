from __future__ import annotations

import uuid

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError, ProtocolError

MAX_STORAGE_BYTES = 2 * 1024 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
_MAX_ID_LENGTH = 256
_MAX_PATH_LENGTH = 1024
_MAX_PATH_SEGMENT_LENGTH = 255


def validated_namespace_id(value: str) -> str:
    return _shared.validated_id(value, "Namespace ID", message="Namespace ID is invalid.")


def validated_resource_id(value: str) -> str:
    parsed: uuid.UUID | None = None
    if isinstance(value, str) and len(value) <= _MAX_ID_LENGTH:
        try:
            parsed = uuid.UUID(value)
        except ValueError:
            pass
    if parsed is None or str(parsed) != value:
        raise ConfigurationError("Resource ID is invalid.")
    return value


def validated_data_path(value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("Resource path is invalid.")
    if value == "" and allow_empty:
        return value
    if (
        not value
        or len(value) > _MAX_PATH_LENGTH
        or value.startswith("/")
        or value.endswith("/")
        or value.startswith("data/")
        or "\\" in value
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Resource path is invalid.")
    if any(
        not part or part in {".", ".."} or len(part) > _MAX_PATH_SEGMENT_LENGTH
        for part in value.split("/")
    ):
        raise ConfigurationError("Resource path is invalid.")
    valid_utf8 = True
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        valid_utf8 = False
    if not valid_utf8:
        raise ConfigurationError("Resource path is invalid.")
    return value


def data_key(path: str, *, allow_empty: bool = False) -> str:
    validated = validated_data_path(path, allow_empty=allow_empty)
    return "data" if not validated else f"data/{validated}"


def validated_server_data_key(value: str) -> str:
    if value == "data":
        return value
    if not isinstance(value, str) or not value.startswith("data/"):
        raise ProtocolError("dicehub returned a resource outside the data root.")
    validated: str | None = None
    try:
        validated = data_key(validated_data_path(value[5:]))
    except ConfigurationError:
        pass
    if validated is None:
        raise ProtocolError("dicehub returned an invalid resource key.")
    return validated


def validated_text(value: str) -> str:
    encoded: bytes | None = None
    if isinstance(value, str):
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError:
            pass
    if encoded is None or len(encoded) > MAX_TEXT_BYTES:
        raise ConfigurationError("Resource text must be valid UTF-8 and at most 2 MiB.")
    return value.replace("\r\n", "\n")


def validated_text_response(value: str) -> str:
    encoded: bytes | None = None
    if isinstance(value, str):
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError:
            pass
    if encoded is None or len(encoded) > MAX_TEXT_BYTES:
        raise ProtocolError("dicehub returned invalid or oversized resource text.")
    return value


def validated_search_filter(value: str | None) -> str | None:
    return _shared.validated_search_filter(value, "Resource")


def validated_offset(value: int) -> int:
    return _shared.validated_offset(value, "Resource")


def validated_page_size(value: int) -> int:
    return _shared.validated_page_size(value, "Resource")


def validated_cursor(value: str | None) -> str | None:
    return _shared.validated_cursor(value, "Resource", printable=True)


def validated_storage_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_STORAGE_BYTES:
        raise ConfigurationError("Storage limit must be between 1 byte and 2 GiB.")
    return value
