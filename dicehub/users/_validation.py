from __future__ import annotations

import re

from dicehub.errors import ConfigurationError

_MAX_ID_LENGTH = 256
_MIN_USERNAME_LENGTH = 3
_MAX_USERNAME_LENGTH = 128
_USERNAME_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{{_MIN_USERNAME_LENGTH},{_MAX_USERNAME_LENGTH}}}")


def validated_namespace_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or value.startswith("0")
        or len(value) > _MAX_ID_LENGTH
    ):
        raise ConfigurationError("Membership namespace ID is invalid.")
    return value


def validated_username(value: str) -> str:
    if not isinstance(value, str) or _USERNAME_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Membership username must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value
