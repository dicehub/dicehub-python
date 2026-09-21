from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from dicehub import (
    APIError,
    AsyncClient,
    Client,
    MembershipVisibility,
    MutationOutcomeUnknownError,
    ProjectMemberTeam,
    ProjectMemberUser,
    ProjectRole,
    ProjectTeamMembership,
    ProjectTeamMembershipPage,
    ProjectUserMembership,
    ProjectUserMembershipPage,
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
        "namespaceId": "91",
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
        "namespaceId": "91",
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
            "projects": {
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
    return {"data": {"projects": {field: {"status": _status()}}}}


def test_list_roles_returns_typed_project_roles() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListProjectRoles"
        assert payload["variables"] == {"projectId": "91"}
        assert "listRolesByProjectId" in payload["query"]
        assert "91" not in payload["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "listRolesByProjectId": {
                            "status": _status(),
                            "roles": [{"roleId": "3", "name": "MAINTAINER"}],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        roles = client.projects.list_roles(project_id="91")

    assert roles == (ProjectRole(role_id="3", name="MAINTAINER"),)


def test_get_role_by_name_requires_one_case_sensitive_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListProjectRoles"
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "listRolesByProjectId": {
                            "status": _status(),
                            "roles": [
                                {"roleId": "3", "name": "MAINTAINER"},
                                {"roleId": "4", "name": "maintainer"},
                            ],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        assert client.projects.get_role_by_name(project_id="91", name="MAINTAINER") == ProjectRole(
            role_id="3",
            name="MAINTAINER",
        )


@pytest.mark.parametrize(
    ("roles", "reason"),
    [
        ([], "NOT_FOUND"),
        (
            [{"roleId": "3", "name": "MAINTAINER"}, {"roleId": "4", "name": "MAINTAINER"}],
            "AMBIGUOUS",
        ),
        ([{"roleId": "3", "name": "maintainer"}], "NOT_FOUND"),
    ],
)
def test_get_role_by_name_rejects_missing_ambiguous_or_case_mismatched_roles(
    roles: list[dict[str, str]],
    reason: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "listRolesByProjectId": {
                            "status": _status(),
                            "roles": roles,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(SelectorResolutionError) as captured:
        client.projects.get_role_by_name(project_id="91", name="MAINTAINER")

    assert captured.value.selector == "role_name"
    assert captured.value.reason == reason


def test_list_user_members_uses_project_contract_without_deduplicate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListProjectUserMemberships"
        assert payload["variables"] == {
            "projectId": "91",
            "includeInherited": False,
            "searchFilter": "ada",
            "offset": 2.0,
            "limit": 5.0,
            "cursor": "opaque",
        }
        assert 'orderBy: "user_id"' in payload["query"]
        assert "$deduplicate" not in payload["query"]
        assert "ada" not in payload["query"]
        return httpx.Response(
            200,
            json=_list_response("listUserMembershipsInProject", [_user_membership()]),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        page = client.projects.list_user_members(
            project_id="91",
            include_inherited=False,
            search_filter="ada",
            offset=2,
            limit=5,
            cursor="opaque",
        )

    assert page == ProjectUserMembershipPage(
        memberships=(
            ProjectUserMembership(
                membership_id="901",
                member_id="7",
                namespace_id="91",
                visibility=MembershipVisibility.PRIVATE,
                role_id="3",
                inherited=False,
                user=ProjectMemberUser(
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


def test_list_team_members_uses_deduplicate_project_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListProjectTeamMemberships"
        assert payload["variables"] == {
            "projectId": "91",
            "includeInherited": True,
            "deduplicate": True,
            "searchFilter": None,
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        assert 'orderBy: "team_id"' in payload["query"]
        return httpx.Response(
            200,
            json=_list_response("listTeamMembershipsInProject", [_team_membership()]),
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        page = client.projects.list_team_members(project_id="91", deduplicate=True)

    assert page == ProjectTeamMembershipPage(
        memberships=(
            ProjectTeamMembership(
                membership_id="902",
                member_id="8",
                namespace_id="91",
                visibility=MembershipVisibility.PUBLIC,
                role_id="4",
                inherited=True,
                team=ProjectMemberTeam(
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
    ("operation_name", "field", "variables"),
    [
        (
            "AddProjectMember",
            "addMemberToProject",
            {
                "projectId": "91",
                "memberId": "7",
                "roleId": "3",
                "visibility": "PUBLIC",
            },
        ),
        (
            "UpdateProjectMember",
            "updateProjectMembership",
            {
                "projectId": "91",
                "memberId": "7",
                "roleId": "4",
                "visibility": "HIDDEN",
            },
        ),
        (
            "RemoveProjectMember",
            "removeMemberFromProject",
            {"projectId": "91", "memberId": "7"},
        ),
    ],
)
def test_member_mutations_use_fixed_id_variables(
    operation_name: str,
    field: str,
    variables: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert "91" not in payload["query"]
        return httpx.Response(200, json=_mutation_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        if operation_name == "AddProjectMember":
            client.projects.add_member(
                project_id="91",
                member_id="7",
                role_id="3",
                visibility=MembershipVisibility.PUBLIC,
            )
        elif operation_name == "UpdateProjectMember":
            client.projects.update_member(
                project_id="91",
                member_id="7",
                role_id="4",
                visibility=MembershipVisibility.HIDDEN,
            )
        else:
            client.projects.remove_member(project_id="91", member_id="7")


@pytest.mark.parametrize(
    "response",
    [
        _list_response("listUserMembershipsInProject", None),
        _list_response(
            "listUserMembershipsInProject",
            [{**_user_membership(), "secret": "x"}],
        ),
        _list_response(
            "listUserMembershipsInProject",
            [{**_user_membership(), "membershipId": "01"}],
        ),
    ],
)
def test_malformed_membership_response_fails_closed(response: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.projects.list_user_members(project_id="91")


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
        client.projects.add_member(project_id="91", member_id="7", role_id="3")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None


def test_member_status_failure_does_not_expose_server_details() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_mutation_response("removeMemberFromProject")
            | {
                "data": {
                    "projects": {
                        "removeMemberFromProject": {
                            "status": _status(succeeded=False, error="sentinel-server-secret")
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.projects.remove_member(project_id="91", member_id="7")

    assert "sentinel-server-secret" not in str(captured.value)


def test_async_project_membership_surface_uses_the_same_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListProjectRoles"
        assert payload["variables"] == {"projectId": "91"}
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "listRolesByProjectId": {
                            "status": _status(),
                            "roles": [{"roleId": "3", "name": "MAINTAINER"}],
                        }
                    }
                }
            },
            request=request,
        )

    async def scenario() -> tuple[ProjectRole, ...]:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.projects.list_roles(project_id="91")

    assert asyncio.run(scenario()) == (ProjectRole(role_id="3", name="MAINTAINER"),)
