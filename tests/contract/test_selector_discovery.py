from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from dicehub import AsyncClient, Client
from dicehub.errors import APIError, ConfigurationError, ProtocolError, SelectorResolutionError
from dicehub.teams import Team
from dicehub.users import MembershipCandidate


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _candidate(*, username: str = "ada", user_id: str = "7") -> dict[str, object]:
    return {
        "userId": user_id,
        "username": username,
    }


def _candidate_response(
    candidates: object,
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "users": {
                "searchMembershipCandidates": {
                    "status": status or _status(),
                    "candidates": candidates,
                }
            }
        }
    }


def _team(*, route: str = "/research/solvers") -> dict[str, object]:
    return {
        "teamId": "8",
        "groupId": "73",
        "name": "Solvers",
        "displayRoute": "research / Solvers",
        "route": route,
    }


def _team_response(
    team: object,
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "teams": {
                "getTeamByRoute": {
                    "team": team,
                    "status": status or _status(),
                }
            }
        }
    }


def test_user_resolution_uses_exact_case_insensitive_match_and_fixed_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert payload["operationName"] == "SearchMembershipCandidates"
        assert payload["variables"] == {
            "namespaceId": "73",
            "searchFilter": "ADA",
        }
        assert "searchMembershipCandidates" in payload["query"]
        assert "firstName" not in payload["query"]
        assert "lastName" not in payload["query"]
        assert "avatarUrl" not in payload["query"]
        assert "ADA" not in payload["query"]
        return httpx.Response(
            200,
            json=_candidate_response([_candidate(username="Ada")]),
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        candidate = client.users.resolve_membership_candidate(
            namespace_id="73",
            username="ADA",
        )

    assert candidate == MembershipCandidate(
        user_id="7",
        username="Ada",
    )


@pytest.mark.parametrize(
    ("candidates", "reason"),
    [
        ([], "NOT_FOUND"),
        ([_candidate(username="ada"), _candidate(username="ADA", user_id="8")], "AMBIGUOUS"),
    ],
)
def test_user_resolution_rejects_zero_or_multiple_exact_matches(
    candidates: list[dict[str, object]],
    reason: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_candidate_response(candidates), request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(SelectorResolutionError) as captured,
    ):
        client.users.resolve_membership_candidate(namespace_id="73", username="ada")

    assert captured.value.as_dict()["reason"] == reason


def test_user_resolution_validates_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ConfigurationError),
    ):
        client.users.resolve_membership_candidate(namespace_id="73", username="ab")

    assert request_count == 0


def test_user_resolution_rejects_incompatible_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_candidate_response([_candidate(user_id="not-a-number")]),
            request=request,
        )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ProtocolError),
    ):
        client.users.resolve_membership_candidate(namespace_id="73", username="ada")


def test_team_resolution_uses_full_route_and_fixed_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert payload["operationName"] == "GetTeamByRoute"
        assert payload["variables"] == {"route": "/research/solvers"}
        assert "getTeamByRoute" in payload["query"]
        assert "/research/solvers" not in payload["query"]
        assert payload["query"].index("      team {") < payload["query"].index("      status {")
        return httpx.Response(200, json=_team_response(_team()), request=request)

    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        team = client.teams.get_by_route(route="/research/solvers")

    assert team == Team(
        team_id="8",
        group_id="73",
        name="Solvers",
        display_route="research / Solvers",
        route="/research/solvers",
    )


def test_team_resolution_validates_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ConfigurationError),
    ):
        client.teams.get_by_route(route="research/solvers")

    assert request_count == 0


def test_team_resolution_rejects_success_without_team() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_team_response(None), request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ProtocolError),
    ):
        client.teams.get_by_route(route="/research/solvers")


def test_async_selector_resolution_matches_sync_contracts() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["operationName"] == "SearchMembershipCandidates":
            response = _candidate_response([_candidate(username="Ada")])
        else:
            assert payload["operationName"] == "GetTeamByRoute"
            response = _team_response(_team())
        return httpx.Response(200, json=response, request=request)

    async def scenario() -> tuple[MembershipCandidate, Team]:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            candidate = await client.users.resolve_membership_candidate(
                namespace_id="73",
                username="ada",
            )
            team = await client.teams.get_by_route(route="/research/solvers")
        return candidate, team

    candidate, team = asyncio.run(scenario())

    assert candidate.username == "Ada"
    assert team.route == "/research/solvers"


def test_user_status_failure_maps_without_exposing_server_value() -> None:
    sentinel = "server-only-detail"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_candidate_response(
                [],
                status={"succeeded": False, "error": sentinel},
            ),
            request=request,
        )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(APIError) as captured,
    ):
        client.users.resolve_membership_candidate(namespace_id="73", username="ada")

    assert captured.value.server_code is None
    assert sentinel not in str(captured.value)
