from __future__ import annotations

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import ProtocolError
from dicehub.teams._graphql import GET_TEAM_BY_ROUTE_QUERY
from dicehub.teams._validation import validated_route
from dicehub.teams.models import Team
from dicehub.teams.service import _team_from_payload, _validated_response


class AsyncTeamsService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def get_by_route(self, *, route: str) -> Team:
        result = await self._graphql.execute(
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
