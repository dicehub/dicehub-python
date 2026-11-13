from __future__ import annotations

import dicehub.teams._rest_async_calls as _rest_calls
from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.rest_v2 import AsyncRestV2Executor
from dicehub._core.status import raise_for_status
from dicehub.errors import ProtocolError
from dicehub.teams._graphql import GET_TEAM_BY_ROUTE_QUERY
from dicehub.teams._validation import validated_route
from dicehub.teams.models import Team
from dicehub.teams.service import _team_from_payload, _validated_response


class AsyncTeamsService:
    def __init__(
        self, graphql: AsyncGraphQLExecutor, *, rest_api: AsyncRestV2Executor | None = None
    ) -> None:
        self._graphql = graphql
        self._rest_api = rest_api

    async def get_by_route(self, *, route: str) -> Team:
        rest_variables: dict[str, object] = {"route": validated_route(route)}
        if self._rest_api is not None:
            return await _rest_calls.get_by_route(self._rest_api, rest_variables)
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
