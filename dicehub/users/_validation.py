from __future__ import annotations

import re

from dicehub._core import validation as _shared
from dicehub.errors import ConfigurationError

_MIN_USERNAME_LENGTH = 3
_MAX_USERNAME_LENGTH = 128
_USERNAME_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{{_MIN_USERNAME_LENGTH},{_MAX_USERNAME_LENGTH}}}")


def validated_namespace_id(value: str) -> str:
    return _shared.validated_id(
        value, "Membership namespace ID", message="Membership namespace ID is invalid."
    )


def validated_username(value: str) -> str:
    if not isinstance(value, str) or _USERNAME_PATTERN.fullmatch(value) is None:
        raise ConfigurationError(
            "Membership username must be 3 to 128 ASCII letters, digits, underscores, or hyphens."
        )
    return value
