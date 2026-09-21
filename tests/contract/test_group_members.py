from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    Client,
    GroupMemberTeam,
    GroupMemberUser,
    GroupRole,
    GroupTeamMembership,
    GroupTeamMembershipPage,
    GroupUserMembership,
    GroupUserMembershipPage,
    MembershipVisibility,
    MutationOutcomeUnknownError,
    ProtocolError,
)


def _client(transport: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    )


def _status() -> dict[str, object]:
    return {"succeeded": True, "error": None}


def _user_membership() -> dict[str, object]:
    return {
        "membershipId": "901",
        "memberId": "7",
        "namespaceId": "73",
        "visibility": "PRIVATE",
        "roleId": "3",
        "inherited": False,
        "user": {
            "userId": "7",
            "firstName": "Ada",
            "lastName": "Lovelace",
            "username": "ada",
            "avatarUrl": None,
        },
    }


def _team_membership() -> dict[str, object]:
    return {
        "membershipId": "902",
        "memberId": "8",
        "namespaceId": "73",
        "visibility": "PUBLIC",
        "roleId": "4",
        "inherited": True,
        "team": {
            "teamId": "8",
            "name": "Solvers",
            "route": "/research/solvers",
            "avatarUrl": "https://dicehub.test/api/v1/teams/8/avatar",
        },
    }


def _list_response(field: str, memberships: object) -> dict[str, object]:
    return {
        "data": {
            "groups": {
                field: {
                    "status": _status(),
                    "info": {"offset": 2.0, "count": 1.0, "cursor": "next"},
                    "userMemberships" if field.startswith("listUser") else "teamMemberships": (
                        memberships
                    ),
                }
            }
        }
    }


def _mutation_response(field: str) -> dict[str, object]:
    return {"data": {"groups": {field: {"status": _status()}}}}


def test_get_role_by_name_returns_one_exact_public_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListGroupRoles"
        assert payload["variables"] == {"groupId": "73"}
        return httpx.Response(
            200,
            json={
                "data": {
                    "groups": {
                        "listRolesByGroupId": {
                            "status": _status(),
                            "roles": [{"roleId": "3", "name": "MAINTAINER"}],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        role = client.groups.get_role_by_name(group_id="73", name="MAINTAINER")

    assert role == GroupRole(role_id="3", name="MAINTAINER")


def test_list_user_members_uses_fixed_pagination_variables() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListGroupUserMemberships"
        assert payload["variables"] == {
            "groupId": "73",
            "includeInherited": False,
            "deduplicate": True,
            "searchFilter": "ada",
            "offset": 2.0,
            "limit": 5.0,
            "cursor": "opaque",
        }
        assert 'orderBy: "user_id"' in payload["query"]
        assert "ada" not in payload["query"]
        return httpx.Response(
            200,
            json=_list_response("listUserMembershipsInGroup", [_user_membership()]),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        page = client.groups.list_user_members(
            group_id="73",
            include_inherited=False,
            deduplicate=True,
            search_filter="ada",
            offset=2,
            limit=5,
            cursor="opaque",
        )

    assert page == GroupUserMembershipPage(
        memberships=(
            GroupUserMembership(
                membership_id="901",
                member_id="7",
                namespace_id="73",
                visibility=MembershipVisibility.PRIVATE,
                role_id="3",
                inherited=False,
                user=GroupMemberUser(
                    user_id="7",
                    first_name="Ada",
                    last_name="Lovelace",
                    username="ada",
                    avatar_url=None,
                ),
            ),
        ),
        offset=2,
        count=1,
        cursor="next",
    )


def test_list_team_members_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListGroupTeamMemberships"
        assert payload["variables"] == {
            "groupId": "73",
            "includeInherited": True,
            "deduplicate": False,
            "searchFilter": None,
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        assert 'orderBy: "team_id"' in payload["query"]
        return httpx.Response(
            200,
            json=_list_response("listTeamMembershipsInGroup", [_team_membership()]),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        page = client.groups.list_team_members(group_id="73")

    assert page == GroupTeamMembershipPage(
        memberships=(
            GroupTeamMembership(
                membership_id="902",
                member_id="8",
                namespace_id="73",
                visibility=MembershipVisibility.PUBLIC,
                role_id="4",
                inherited=True,
                team=GroupMemberTeam(
                    team_id="8",
                    name="Solvers",
                    route="/research/solvers",
                    avatar_url="https://dicehub.test/api/v1/teams/8/avatar",
                ),
            ),
        ),
        offset=2,
        count=1,
        cursor="next",
    )


@pytest.mark.parametrize(
    ("operation", "field", "variables"),
    [
        (
            "add",
            "addMemberToGroup",
            {
                "groupId": "73",
                "memberId": "7",
                "roleId": "3",
                "visibility": "PUBLIC",
            },
        ),
        (
            "update",
            "updateGroupMembership",
            {
                "groupId": "73",
                "memberId": "7",
                "roleId": "4",
                "visibility": "HIDDEN",
            },
        ),
        (
            "remove",
            "removeMemberFromGroup",
            {"groupId": "73", "memberId": "7"},
        ),
    ],
)
def test_member_mutations_use_fixed_variables(
    operation: str,
    field: str,
    variables: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["variables"] == variables
        assert payload["operationName"].lower().startswith(operation)
        assert "73" not in payload["query"]
        return httpx.Response(200, json=_mutation_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        if operation == "add":
            client.groups.add_member(
                group_id="73",
                member_id="7",
                role_id="3",
                visibility=MembershipVisibility.PUBLIC,
            )
        elif operation == "update":
            client.groups.update_member(
                group_id="73",
                member_id="7",
                role_id="4",
                visibility=MembershipVisibility.HIDDEN,
            )
        else:
            client.groups.remove_member(group_id="73", member_id="7")


@pytest.mark.parametrize(
    "response",
    [
        _list_response("listUserMembershipsInGroup", None),
        _list_response("listUserMembershipsInGroup", [{**_user_membership(), "secret": "x"}]),
        _list_response(
            "listUserMembershipsInGroup",
            [{**_user_membership(), "membershipId": "01"}],
        ),
    ],
)
def test_malformed_membership_response_fails_closed(response: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.groups.list_user_members(group_id="73")


def test_member_mutation_is_not_retried_after_transport_failure() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.ConnectError("sentinel transport details", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.groups.add_member(group_id="73", member_id="7", role_id="3")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
