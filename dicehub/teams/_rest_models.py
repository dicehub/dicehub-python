"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel


class TeamSummary(WireModel):
    team_id: str
    group_id: str | None
    name: str
    route: str | None
    display_route: str


class TeamDetail(WireModel):
    team_id: str
    name: str
    group_id: str | None
    description: str | None
    route: str | None
    display_route: str
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"] | None
    avatar_url: str | None
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None
