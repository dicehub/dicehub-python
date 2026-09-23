from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    ConfigurationError,
    Project,
    ProjectDetail,
    ProjectOrderField,
    ProjectPage,
    ProjectVisibility,
    ProtocolError,
    SortOrder,
)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _session_client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    projects: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 0.0, "count": 2.0, "cursor": "cursor-value"}
    if projects is ...:
        projects = [
            {
                "projectId": "91",
                "groupId": "42",
                "name": "Airfoil",
                "displayRoute": "ros / Airfoil",
                "route": "/ros/airfoil",
                "visibility": "PRIVATE",
            },
            {
                "projectId": "92",
                "groupId": "42",
                "name": "Hull",
                "displayRoute": "ros / Hull",
                "route": "/ros/hull",
                "visibility": "PUBLIC",
            },
        ]
    return {
        "data": {
            "projects": {
                "listProjects": {
                    "status": status or _status(),
                    "info": info,
                    "projects": projects,
                }
            }
        }
    }


def _project_detail() -> dict[str, object]:
    return {
        "projectId": "91",
        "groupId": "42",
        "name": "Airfoil",
        "displayRoute": "ros / Airfoil",
        "route": "/ros/airfoil",
        "visibility": "PRIVATE",
        "description": "Transient study",
        "avatarUrl": None,
    }


def _single_response(field: str) -> dict[str, object]:
    return {
        "data": {
            "projects": {
                field: {
                    "status": _status(),
                    "project": _project_detail(),
                }
            }
        }
    }


def _default_response(field: str) -> dict[str, object]:
    return {"data": {"projects": {field: {"status": _status()}}}}


def test_list_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListProjects"
        assert payload["variables"] == {
            "userId": "7",
            "groupId": "42",
            "searchFilter": "foil",
            "orderBy": "updated_at",
            "order": "DESC",
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        assert "listProjects" in payload["query"]
        assert "description" not in payload["query"]
        assert "avatarUrl" not in payload["query"]
        assert "$userId" in payload["query"]
        return httpx.Response(200, json=_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.projects.list(
            user_id="7",
            group_id="42",
            search_filter="foil",
            order_by=ProjectOrderField.UPDATED_AT,
            order=SortOrder.DESC,
        )

    assert page == ProjectPage(
        projects=(
            Project(
                project_id="91",
                group_id="42",
                name="Airfoil",
                display_route="ros / Airfoil",
                route="/ros/airfoil",
                visibility=ProjectVisibility.PRIVATE,
            ),
            Project(
                project_id="92",
                group_id="42",
                name="Hull",
                display_route="ros / Hull",
                route="/ros/hull",
                visibility=ProjectVisibility.PUBLIC,
            ),
        ),
        offset=0,
        count=2,
        cursor="cursor-value",
    )


def test_list_accepts_routes_longer_than_legacy_ui_assumptions() -> None:
    route = "/" + "a" * 2048
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(
                info={"offset": 0.0, "count": 1.0, "cursor": "cursor"},
                projects=[
                    {
                        "projectId": "91",
                        "groupId": "42",
                        "name": "Airfoil",
                        "displayRoute": route,
                        "route": route,
                        "visibility": "PRIVATE",
                    }
                ],
            ),
            request=request,
        )
    )

    with _client(transport) as client:
        page = client.projects.list()

    assert page.projects[0].route == route
    assert page.projects[0].display_route == route


def test_list_maps_status_failure_without_server_details() -> None:
    server_error = "sentinel-server-secret"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(
                status=_status(succeeded=False, error=server_error),
                info=None,
                projects=None,
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.projects.list()

    assert server_error not in str(captured.value)


@pytest.mark.parametrize(
    ("info", "projects"),
    [
        (None, []),
        ({"offset": 0.5, "count": 1.0, "cursor": "cursor"}, []),
        ({"offset": 0.0, "count": 1.0, "cursor": "cursor"}, None),
        (
            {"offset": 0.0, "count": 1.0, "cursor": "cursor"},
            [
                {
                    "projectId": "01",
                    "groupId": "42",
                    "name": "Airfoil",
                    "displayRoute": "ros / Airfoil",
                    "route": "/ros/airfoil",
                    "visibility": "PRIVATE",
                }
            ],
        ),
    ],
)
def test_list_rejects_incompatible_success_payload(info: object, projects: object) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(info=info, projects=projects),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.projects.list()

    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    ("method_name", "argument", "operation_name", "field"),
    [
        ("get", {"project_id": "91"}, "GetProject", "getProjectById"),
        (
            "get_by_route",
            {"route": "/ros/airfoil"},
            "GetProjectByRoute",
            "getProjectByRoute",
        ),
    ],
)
def test_get_operations_return_project_details(
    method_name: str,
    argument: dict[str, str],
    operation_name: str,
    field: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == {
            "projectId" if method_name == "get" else "route": next(iter(argument.values()))
        }
        assert field in payload["query"]
        assert next(iter(argument.values())) not in payload["query"]
        if method_name == "get_by_route":
            assert payload["query"].index("project {") < payload["query"].index("status {")
        return httpx.Response(200, json=_single_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        project = getattr(client.projects, method_name)(**argument)

    assert project == ProjectDetail(
        project_id="91",
        group_id="42",
        name="Airfoil",
        display_route="ros / Airfoil",
        route="/ros/airfoil",
        visibility=ProjectVisibility.PRIVATE,
        description="Transient study",
        avatar_url=None,
    )


def test_create_uses_fixed_variables_and_returns_common_project_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        assert payload["operationName"] == "CreateProject"
        assert payload["variables"] == {
            "name": "Case $name",
            "slug": "case_01",
            "description": "line one\nline two",
            "groupId": "42",
            "visibility": "INTERNAL",
        }
        assert "Case $name" not in payload["query"]
        assert "groupType" not in payload["query"]
        assert "createdAt" not in payload["query"]
        assert "updatedAt" not in payload["query"]
        return httpx.Response(200, json=_single_response("createProject"), request=request)

    with _session_client(httpx.MockTransport(handler)) as client:
        created = client.projects.create(
            name="Case $name",
            slug="case_01",
            description="line one\nline two",
            group_id="42",
            visibility=ProjectVisibility.INTERNAL,
        )

    assert isinstance(created, ProjectDetail)
    assert created.project_id == "91"


@pytest.mark.parametrize("group_id", [None, "42"])
def test_api_key_create_uses_fixed_personal_or_group_destination(
    group_id: str | None,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "CreateProject"
        assert payload["variables"] == {
            "name": "Agent project",
            "slug": "agent-project",
            "description": None,
            "groupId": group_id,
            "visibility": "PRIVATE",
        }
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_single_response("createProject"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        created = client.projects.create(
            name="Agent project",
            slug="agent-project",
            group_id=group_id,
        )

    assert created.project_id == "91"


def test_update_can_clear_description() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "UpdateProject"
        assert payload["variables"] == {
            "projectId": "91",
            "name": None,
            "slug": None,
            "description": "",
            "visibility": None,
        }
        return httpx.Response(200, json=_default_response("updateProject"), request=request)

    with _session_client(httpx.MockTransport(handler)) as client:
        client.projects.update(project_id="91", description="")


def test_api_key_can_update_a_permission_scoped_project() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "UpdateProject"
        assert payload["variables"] == {
            "projectId": "91",
            "name": "Updated project",
            "slug": None,
            "description": None,
            "visibility": None,
        }
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_default_response("updateProject"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.projects.update(project_id="91", name="Updated project")


def test_api_key_can_delete_a_permission_scoped_project() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "DeleteProject"
        assert payload["variables"] == {"projectId": "91"}
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_default_response("deleteProject"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.projects.delete(project_id="91")


@pytest.mark.parametrize(
    ("method_name", "kwargs", "operation_name", "response_field", "variables"),
    [
        (
            "move",
            {"project_id": "91", "to_group_id": "43"},
            "MoveProject",
            "moveProject",
            {"projectId": "91", "toGroupId": "43"},
        ),
        (
            "delete",
            {"project_id": "91"},
            "DeleteProject",
            "deleteProject",
            {"projectId": "91"},
        ),
    ],
)
def test_lifecycle_mutations_use_fixed_operations(
    method_name: str,
    kwargs: dict[str, str],
    operation_name: str,
    response_field: str,
    variables: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert response_field in payload["query"]
        return httpx.Response(200, json=_default_response(response_field), request=request)

    with _session_client(httpx.MockTransport(handler)) as client:
        getattr(client.projects, method_name)(**kwargs)


def test_api_keys_cannot_start_session_only_project_move() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError, match="Project move requires"),
    ):
        client.projects.move(project_id="91", to_group_id="42")

    assert request_count == 0
