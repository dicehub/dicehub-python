from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    AppMemberTeam,
    AppMemberUser,
    AppRole,
    AppTeamMembership,
    AppTeamMembershipPage,
    AppUserMembership,
    AppUserMembershipPage,
    Client,
    MembershipVisibility,
    MutationOutcomeUnknownError,
    ProtocolError,
    SelectorResolutionError,
)


def _client(transport: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _user_membership() -> dict[str, object]:
    return {
        "membershipId": "901",
        "memberId": "7",
        "namespaceId": "101",
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
        "namespaceId": "101",
        "visibility": "PUBLIC",
        "roleId": "4",
        "inherited": True,
        "team": {
            "teamId": "8",
            "name": "Solvers",
            "route": "/research/solvers",
            "avatarUrl": None,
        },
    }


def _list_response(field: str, memberships: object) -> dict[str, object]:
    key = "userMemberships" if field.startswith("listUser") else "teamMemberships"
    return {
        "data": {
            "apps": {
                field: {
                    "status": _status(),
                    "info": {"offset": 2.0, "count": 1.0, "cursor": "next"},
                    key: memberships,
                }
            }
        }
    }


def _roles_response(roles: object) -> dict[str, object]:
    return {
        "data": {
            "apps": {
                "listRolesByAppId": {
                    "status": _status(),
                    "roles": roles,
                }
            }
        }
    }


def _mutation_response(
    field: str,
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {"data": {"apps": {field: {"status": status or _status()}}}}


def test_roles_are_typed_and_name_lookup_is_exact_case_sensitive() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListAppRoles"
        assert payload["variables"] == {"appId": "101"}
        assert "listRolesByAppId" in payload["query"]
        assert "101" not in payload["query"]
        return httpx.Response(
            200,
            json=_roles_response(
                [
                    {"roleId": "3", "name": "EDITOR"},
                    {"roleId": "4", "name": "editor"},
                ]
            ),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        roles = client.apps.list_roles(app_id="101")
        selected = client.apps.get_role_by_name(app_id="101", name="EDITOR")

    assert roles == (
        AppRole(role_id="3", name="EDITOR"),
        AppRole(role_id="4", name="editor"),
    )
    assert selected == AppRole(role_id="3", name="EDITOR")


def test_role_lookup_rejects_a_case_mismatched_name() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_roles_response([{"roleId": "3", "name": "EDITOR"}]),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(SelectorResolutionError) as captured:
        client.apps.get_role_by_name(app_id="101", name="editor")

    assert captured.value.selector == "role_name"
    assert captured.value.reason == "NOT_FOUND"


def test_membership_pages_use_app_fields_and_return_strict_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["operationName"] == "ListAppUserMemberships":
            assert payload["variables"] == {
                "appId": "101",
                "includeInherited": False,
                "searchFilter": "ada",
                "offset": 2.0,
                "limit": 5.0,
                "cursor": "opaque",
            }
            assert "listUserMembershipsInApp" in payload["query"]
            assert "$deduplicate" not in payload["query"]
            return httpx.Response(
                200,
                json=_list_response("listUserMembershipsInApp", [_user_membership()]),
                request=request,
            )
        assert payload["operationName"] == "ListAppTeamMemberships"
        assert payload["variables"] == {
            "appId": "101",
            "includeInherited": True,
            "deduplicate": True,
            "searchFilter": None,
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        assert "listTeamMembershipsInApp" in payload["query"]
        return httpx.Response(
            200,
            json=_list_response("listTeamMembershipsInApp", [_team_membership()]),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        user_page = client.apps.list_user_members(
            app_id="101",
            include_inherited=False,
            search_filter="ada",
            offset=2,
            limit=5,
            cursor="opaque",
        )
        team_page = client.apps.list_team_members(app_id="101", deduplicate=True)

    assert user_page == AppUserMembershipPage(
        memberships=(
            AppUserMembership(
                membership_id="901",
                member_id="7",
                namespace_id="101",
                role_id="3",
                visibility=MembershipVisibility.PRIVATE,
                inherited=False,
                user=AppMemberUser(
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
    assert team_page == AppTeamMembershipPage(
        memberships=(
            AppTeamMembership(
                membership_id="902",
                member_id="8",
                namespace_id="101",
                role_id="4",
                visibility=MembershipVisibility.PUBLIC,
                inherited=True,
                team=AppMemberTeam(
                    team_id="8",
                    name="Solvers",
                    route="/research/solvers",
                    avatar_url=None,
                ),
            ),
        ),
        offset=2,
        count=1,
        cursor="next",
    )


@pytest.mark.parametrize(
    ("method", "operation_name", "field", "variables"),
    [
        (
            "add_member",
            "AddAppMember",
            "addMemberToApp",
            {
                "appId": "101",
                "memberId": "7",
                "roleId": "3",
                "visibility": "PRIVATE",
            },
        ),
        (
            "update_member",
            "UpdateAppMember",
            "updateAppMembership",
            {
                "appId": "101",
                "memberId": "7",
                "roleId": "4",
                "visibility": "HIDDEN",
            },
        ),
        (
            "remove_member",
            "RemoveAppMember",
            "removeMemberFromApp",
            {"appId": "101", "memberId": "7"},
        ),
    ],
)
def test_member_mutations_use_fixed_id_variables(
    method: str,
    operation_name: str,
    field: str,
    variables: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert field in payload["query"]
        assert "101" not in payload["query"]
        return httpx.Response(200, json=_mutation_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        if method == "add_member":
            client.apps.add_member(
                app_id="101",
                member_id="7",
                role_id="3",
            )
        elif method == "update_member":
            client.apps.update_member(
                app_id="101",
                member_id="7",
                role_id="4",
                visibility=MembershipVisibility.HIDDEN,
            )
        else:
            client.apps.remove_member(app_id="101", member_id="7")


@pytest.mark.parametrize(
    ("response", "method"),
    [
        (_roles_response(None), "list_roles"),
        (_list_response("listUserMembershipsInApp", None), "list_user_members"),
        (_list_response("listTeamMembershipsInApp", None), "list_team_members"),
    ],
)
def test_malformed_collection_fails_closed(response: dict[str, object], method: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=response,
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        getattr(client.apps, method)(app_id="101")


def test_member_status_failure_is_sanitized() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_mutation_response(
                "removeMemberFromApp",
                status=_status(succeeded=False, error="sentinel-server-secret"),
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.apps.remove_member(app_id="101", member_id="7")

    assert "sentinel-server-secret" not in str(captured.value)


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
        client.apps.add_member(app_id="101", member_id="7", role_id="3")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "app ID 101" in str(captured.value)
    assert "member ID 7" in str(captured.value)
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
