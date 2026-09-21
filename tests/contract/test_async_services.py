from __future__ import annotations

import asyncio
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import pytest

from dicehub import (
    AppDetail,
    AppRole,
    AsyncClient,
    AuthContext,
    Config,
    GroupDetail,
    IdentityMode,
    NamespacePermission,
    ProjectDetail,
    Resource,
    Team,
    Template,
    User,
)

RESOURCE_ID = "12345678-1234-5678-9234-567812345678"
_STATUS = {"succeeded": True, "error": None}


@dataclass(frozen=True)
class _ServiceCase:
    name: str
    call: Callable[[AsyncClient], Awaitable[object]]
    operation_name: str
    variables: dict[str, object]
    query_field: str
    response: dict[str, object]
    expected_type: type[object]
    expected_attribute: str | None
    expected_value: object


def _response(
    domain: str,
    field: str,
    value_name: str,
    value: object,
) -> dict[str, object]:
    return {
        "data": {
            domain: {
                field: {
                    "status": _STATUS,
                    value_name: value,
                }
            }
        }
    }


_SERVICE_CASES = (
    _ServiceCase(
        name="auth",
        call=lambda client: client.auth.context(),
        operation_name="GetAuthContext",
        variables={},
        query_field="identityMode",
        response=_response(
            "authentications",
            "getAuthContext",
            "authContext",
            {"identityMode": "SESSION"},
        ),
        expected_type=AuthContext,
        expected_attribute="identity_mode",
        expected_value=IdentityMode.SESSION,
    ),
    _ServiceCase(
        name="api_keys",
        call=lambda client: client.api_keys.list_permissions(namespace_id="42"),
        operation_name="ListApiKeyPermissions",
        variables={"namespaceId": "42"},
        query_field="listApiKeyPermissions",
        response=_response(
            "apiKeys",
            "listApiKeyPermissions",
            "permissions",
            ["VIEW_USER_PROFILE"],
        ),
        expected_type=tuple,
        expected_attribute=None,
        expected_value=(NamespacePermission.VIEW_USER_PROFILE,),
    ),
    _ServiceCase(
        name="apps",
        call=lambda client: client.apps.get(app_id="101"),
        operation_name="GetApp",
        variables={"appId": "101"},
        query_field="getAppById",
        response=_response(
            "apps",
            "getAppById",
            "app",
            {
                "appId": "101",
                "projectId": "41",
                "name": "Wind tunnel",
                "displayRoute": "engineering / Wind tunnel",
                "route": "/engineering/wind-tunnel",
                "visibility": "PRIVATE",
                "appType": "REGULAR",
                "description": "Transient CFD study",
                "templateId": "9",
                "templateName": "OpenFOAM",
                "templateVersion": "v13",
                "templateSlug": "openfoam",
                "iconPath": None,
                "previewUrl": None,
            },
        ),
        expected_type=AppDetail,
        expected_attribute="app_id",
        expected_value="101",
    ),
    _ServiceCase(
        name="app_roles",
        call=lambda client: client.apps.list_roles(app_id="101"),
        operation_name="ListAppRoles",
        variables={"appId": "101"},
        query_field="listRolesByAppId",
        response=_response(
            "apps",
            "listRolesByAppId",
            "roles",
            [{"roleId": "3", "name": "EDITOR"}],
        ),
        expected_type=tuple,
        expected_attribute=None,
        expected_value=(AppRole(role_id="3", name="EDITOR"),),
    ),
    _ServiceCase(
        name="configs",
        call=lambda client: client.configs.get(config_id="301"),
        operation_name="GetConfig",
        variables={"configId": "301"},
        query_field="getSingleConfigById",
        response=_response(
            "configs",
            "getSingleConfigById",
            "config",
            {
                "configId": "301",
                "appId": "101",
                "configInternalId": "7",
                "name": "Baseline",
                "description": "Reference setup",
                "isDefault": True,
                "templateVersion": "v13",
                "updating": False,
            },
        ),
        expected_type=Config,
        expected_attribute="config_id",
        expected_value="301",
    ),
    _ServiceCase(
        name="groups",
        call=lambda client: client.groups.get(group_id="73"),
        operation_name="GetGroup",
        variables={"groupId": "73"},
        query_field="getGroupById",
        response=_response(
            "groups",
            "getGroupById",
            "group",
            {
                "groupId": "73",
                "parentId": "42",
                "name": "Research",
                "displayRoute": "dicehub / Research",
                "route": "/dicehub/research",
                "visibility": "PRIVATE",
                "hasChildren": True,
                "description": "Simulation research group.",
                "avatarUrl": None,
            },
        ),
        expected_type=GroupDetail,
        expected_attribute="group_id",
        expected_value="73",
    ),
    _ServiceCase(
        name="projects",
        call=lambda client: client.projects.get(project_id="91"),
        operation_name="GetProject",
        variables={"projectId": "91"},
        query_field="getProjectById",
        response=_response(
            "projects",
            "getProjectById",
            "project",
            {
                "projectId": "91",
                "groupId": "42",
                "name": "Airfoil",
                "displayRoute": "ros / Airfoil",
                "route": "/ros/airfoil",
                "visibility": "PRIVATE",
                "description": "Transient study",
                "avatarUrl": None,
            },
        ),
        expected_type=ProjectDetail,
        expected_attribute="project_id",
        expected_value="91",
    ),
    _ServiceCase(
        name="resources",
        call=lambda client: client.resources.get(resource_id=RESOURCE_ID),
        operation_name="GetResource",
        variables={"resourceId": RESOURCE_ID},
        query_field="getResourceById",
        response=_response(
            "resources",
            "getResourceById",
            "resource",
            {
                "resourceId": RESOURCE_ID,
                "namespaceId": "101",
                "key": "data/config/controlDict",
                "resourceType": "TEXT",
            },
        ),
        expected_type=Resource,
        expected_attribute="resource_id",
        expected_value=RESOURCE_ID,
    ),
    _ServiceCase(
        name="teams",
        call=lambda client: client.teams.get_by_route(route="/research/solvers"),
        operation_name="GetTeamByRoute",
        variables={"route": "/research/solvers"},
        query_field="getTeamByRoute",
        response=_response(
            "teams",
            "getTeamByRoute",
            "team",
            {
                "teamId": "8",
                "groupId": "42",
                "name": "Solvers",
                "displayRoute": "Research / Solvers",
                "route": "/research/solvers",
            },
        ),
        expected_type=Team,
        expected_attribute="team_id",
        expected_value="8",
    ),
    _ServiceCase(
        name="templates",
        call=lambda client: client.templates.get(template_id="91"),
        operation_name="GetTemplate",
        variables={"templateId": "91"},
        query_field="getTemplateById",
        response=_response(
            "templates",
            "getTemplateById",
            "template",
            {
                "templateId": "91",
                "name": "OpenFOAM",
                "slug": "openfoam",
                "description": None,
                "clientType": "openfoam",
                "route": "/templates/openfoam",
                "imagePath": None,
                "iconPath": None,
                "tags": [],
                "createdAt": None,
                "updatedAt": None,
            },
        ),
        expected_type=Template,
        expected_attribute="template_id",
        expected_value="91",
    ),
    _ServiceCase(
        name="users",
        call=lambda client: client.users.me(),
        operation_name="WhoAmI",
        variables={},
        query_field="username",
        response=_response(
            "users",
            "me",
            "user",
            {"userId": "7", "username": "ros"},
        ),
        expected_type=User,
        expected_attribute="user_id",
        expected_value="7",
    ),
)


@pytest.mark.parametrize("case", _SERVICE_CASES, ids=lambda case: case.name)
def test_async_service_uses_fixed_contract_and_returns_typed_result(
    case: _ServiceCase,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        assert "authorization" not in request.headers
        assert payload["operationName"] == case.operation_name
        assert payload["variables"] == case.variables
        assert case.query_field in payload["query"]
        return httpx.Response(200, json=case.response, request=request)

    async def scenario() -> object:
        async with AsyncClient(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await case.call(client)

    result = asyncio.run(scenario())

    assert isinstance(result, case.expected_type)
    if case.expected_attribute is None:
        assert result == case.expected_value
    else:
        assert getattr(result, case.expected_attribute) == case.expected_value


def test_async_config_file_download_uses_fixed_rest_path() -> None:
    destination = io.BytesIO()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == ("https://dicehub.test/api/v1/configs/301/files/system/controlDict")
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        return httpx.Response(200, content=b"application yaml", request=request)

    async def scenario() -> int:
        async with AsyncClient(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.configs.download_file(
                config_id="301",
                path="system/controlDict",
                destination=destination,
            )

    count = asyncio.run(scenario())

    assert count == len(b"application yaml")
    assert destination.getvalue() == b"application yaml"
