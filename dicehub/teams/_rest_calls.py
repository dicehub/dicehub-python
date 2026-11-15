"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.teams._rest_models as wire_models
import dicehub.teams.models as models
from dicehub._core.rest_models import (
    convert,
    query_params,
)
from dicehub._core.rest_request import request
from dicehub._core.rest_v2 import RestV2Executor


def get_by_route(rest: RestV2Executor, variables: dict[str, object]) -> models.Team:
    wire = request(
        rest,
        wire_models.TeamSummary,
        method="GET",
        path="api/v2/teams/by-route",
        params=query_params({"route": variables.get("route"), "view": "summary"}),
    )
    return convert(models.Team, wire, ("team_id", "group_id", "name", "display_route", "route"))
