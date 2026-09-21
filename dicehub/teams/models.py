from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Team(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(min_length=1, max_length=256)
    group_id: str | None = Field(default=None, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(min_length=1, max_length=16_384)
    route: str = Field(min_length=1, max_length=16_384)
