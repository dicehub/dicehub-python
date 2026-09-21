from __future__ import annotations

from dicehub.errors import ConfigurationError

_MAX_ROUTE_LENGTH = 16_384


def validated_route(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > _MAX_ROUTE_LENGTH
        or any(not character.isprintable() for character in value)
    ):
        raise ConfigurationError("Team route is invalid.")
    return value
