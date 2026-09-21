from __future__ import annotations

from pydantic import ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import ProtocolError
from dicehub.teams._graphql import (
    GET_TEAM_BY_ROUTE_QUERY,
    GetTeamByRouteData,
    TeamPayload,
)
from dicehub.teams._validation import validated_route
from dicehub.teams.models import Team


class TeamsService:
    def __init__(self, graphql: GraphQLExecutor) -> None:
        self._graphql = graphql

    def get_by_route(self, *, route: str) -> Team:
        result = self._graphql.execute(
            operation_name="GetTeamByRoute",
            query=GET_TEAM_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(result.data)
        payload = response.teams.get_team
        raise_for_status(payload.status)
        if payload.team is None:
            raise ProtocolError("dicehub returned a successful response without a team.")
        return _team_from_payload(payload.team)


def _validated_response(data: dict[str, object]) -> GetTeamByRouteData:
    response: GetTeamByRouteData | None = None
    try:
        response = GetTeamByRouteData.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError("dicehub returned an incompatible team response.")
    return response


def _team_from_payload(payload: TeamPayload) -> Team:
    return Team(
        team_id=payload.team_id,
        group_id=payload.group_id,
        name=payload.name,
        display_route=payload.display_route,
        route=payload.route,
    )
