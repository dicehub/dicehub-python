from __future__ import annotations

import httpx
import pytest

from dicehub import APIError, Client, ConfigurationError, ProjectVisibility


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"group_id": "01"},
        {"user_id": "user"},
        {"group_id": "group"},
        {"search_filter": "bad\nfilter"},
        {"offset": -1},
        {"offset": 2**53},
        {"offset": 10**400},
        {"limit": 0},
        {"limit": 51},
        {"cursor": "bad cursor"},
        {"order_by": "name"},
        {"order": "ASC"},
    ],
)
def test_list_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.projects.list(**kwargs)  # type: ignore[arg-type]

    assert request_count == 0


@pytest.mark.parametrize(
    "project_id",
    ["", "0", "01", "+1", "one", " 1", "1 ", "\u0661"],
)
def test_get_validates_project_id_before_transport(project_id: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.projects.get(project_id=project_id)

    assert request_count == 0


@pytest.mark.parametrize(
    "route",
    ["", "ros/project", "/ros/\nproject", "/ros/\0project", "/" + "x" * 16_384],
)
def test_get_by_route_rejects_unsafe_or_oversized_values(route: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.projects.get_by_route(route=route)

    assert request_count == 0


@pytest.mark.parametrize(
    "route",
    ["/", "/ab/project", "/ros/", "/ros//project", "/rös/project", "/ros/project."],
)
def test_get_by_route_allows_existing_server_route_shapes(route: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "getProjectByRoute": {
                            "status": {"succeeded": False, "error": "NOT_FOUND"},
                            "project": None,
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(APIError):
        client.projects.get_by_route(route=route)


def test_create_accepts_multiline_and_empty_descriptions() -> None:
    descriptions = iter(["line one\nline two", ""])

    def handler(request: httpx.Request) -> httpx.Response:
        description = next(descriptions)
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {
                        "createProject": {
                            "status": {"succeeded": True, "error": None},
                            "project": {
                                "projectId": "91",
                                "groupId": "42",
                                "name": "Case",
                                "displayRoute": "ros / Case",
                                "route": "/ros/case",
                                "visibility": "PRIVATE",
                                "description": description,
                                "avatarUrl": None,
                            },
                        }
                    }
                }
            },
            request=request,
        )

    transport = httpx.MockTransport(handler)
    with Client(
        base_url="https://dicehub.test",
        session_cookie="session",
        transport=transport,
    ) as client:
        for description in ("line one\nline two", ""):
            result = client.projects.create(
                name="Case",
                slug="case",
                description=description,
                visibility=ProjectVisibility.PRIVATE,
            )
            assert result.description == description
