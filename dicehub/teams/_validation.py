from __future__ import annotations

from dicehub._core import validation as _shared


def validated_route(value: str) -> str:
    return _shared.validated_route(value, "Team")
