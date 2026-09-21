from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

GET_TEAM_BY_ROUTE_QUERY = """
query GetTeamByRoute($route: String!) {
  teams {
    getTeamByRoute(route: $route) {
      team {
        teamId
        groupId
        name
        displayRoute
        route
      }
      status {
        succeeded
        error
      }
    }
  }
}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


def _valid_printable(value: str, *, max_length: int) -> bool:
    return 0 < len(value) <= max_length and all(character.isprintable() for character in value)


class TeamPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    group_id: str | None = Field(alias="groupId", default=None, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(alias="displayRoute", min_length=1, max_length=16_384)
    route: str = Field(min_length=1, max_length=16_384)

    @field_validator("team_id", "group_id")
    @classmethod
    def validate_ids(cls, value: str | None) -> str | None:
        if value is not None and not _valid_positive_id(value):
            raise ValueError("invalid team namespace ID")
        return value

    @field_validator("name", "display_route")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not _valid_printable(value, max_length=16_384):
            raise ValueError("invalid team text")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        if not value.startswith("/") or not _valid_printable(value, max_length=16_384):
            raise ValueError("invalid team route")
        return value


class SingleTeamPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    team: TeamPayload | None


class GetTeamByRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_team: SingleTeamPayload = Field(alias="getTeamByRoute")


class GetTeamByRouteData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    teams: GetTeamByRoute
