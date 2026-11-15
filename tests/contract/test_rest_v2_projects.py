from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    ConfigurationError,
    HTTPError,
    ProjectDetail,
    ProjectOrderField,
    ProjectPage,
    ProtocolError,
    SortOrder,
    TransportError,
)


def project() -> dict[str, object]:
    return {
        "project_id": "9007199254740993",
        "group_id": "42",
        "name": "Cooling plate",
        "description": None,
        "visibility": "PRIVATE",
        "route": "/ros/cooling",
        "display_route": "ros / Cooling plate",
        "avatar_url": "https://dicehub.test/avatar.png",
        "created_at": "2026-10-03T10:00:00Z",
        "updated_at": "2026-10-03T11:00:00+00:00",
    }


def summary() -> dict[str, object]:
    return {
        k: v
        for k, v in project().items()
        if k
        in {
            "project_id",
            "group_id",
            "name",
            "visibility",
            "route",
            "display_route",
        }
    }


def page() -> dict[str, object]:
    return {
        "items": [summary()],
        "limit": 1,
        "offset": 0,
        "has_more": True,
        "count": 2,
        "cursor": "opaque+cursor/==",
    }


def client(handler: Callable[[httpx.Request], httpx.Response]) -> Client:
    return Client(
        base_url="https://dicehub.test",
        project_reads="rest_v2",
        transport=httpx.MockTransport(handler),
        api_key="test-key",
    )


def test_rest_project_reads_use_existing_models_credentials_and_fixed_routes() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "dicehub.test"
        assert request.headers["accept-encoding"] == "identity"
        assert request.headers["authorization"] == "Bearer test-key"
        assert "cookie" not in request.headers
        body = page() if request.url.path == "/api/v2/projects" else project()
        return httpx.Response(200, json=body)

    route = "/ros/日本語?x=1&api_key=untrusted#fragment"
    with client(handler) as sdk:
        result = sdk.projects.list(
            user_id="7",
            group_id="42",
            search_filter="a&b 日本語",
            order_by=ProjectOrderField.UPDATED_AT,
            order=SortOrder.DESC,
            limit=1,
            cursor="",
        )
        detail = sdk.projects.get(project_id="9007199254740993")
        same = sdk.projects.get_by_route(route=route)
    assert isinstance(result, ProjectPage)
    assert isinstance(detail, ProjectDetail)
    assert same == detail
    assert result.projects[0].project_id == detail.project_id
    assert detail.avatar_url == "https://dicehub.test/avatar.png"
    assert result.count == 2 and result.cursor == "opaque+cursor/=="
    assert dict(requests[0].url.params) == {
        "view": "summary",
        "user_id": "7",
        "group_id": "42",
        "search": "a&b 日本語",
        "order_by": "updated_at",
        "order": "DESC",
        "limit": "1",
        "offset": "0",
        "cursor": "",
    }
    assert requests[1].url.path == "/api/v2/projects/9007199254740993"
    assert dict(requests[2].url.params) == {"route": route}


def test_pagination_preserves_server_cursor_offset_and_count() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = page()
        if len(requests) == 2:
            assert request.url.params["cursor"] == "opaque+cursor/=="
            assert request.url.params["offset"] == "1"
            body.update(
                items=[{**summary(), "project_id": "9007199254740994"}],
                offset=1,
                has_more=False,
                cursor="last-cursor",
            )
        return httpx.Response(200, json=body)

    with client(handler) as sdk:
        first = sdk.projects.list(limit=1)
        second = sdk.projects.list(limit=1, offset=1, cursor=first.cursor)
    assert len(requests) == 2
    assert second.offset == 1 and second.count == 2
    assert first.projects != second.projects


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, AuthenticationError),
        (403, APIError),
        (302, HTTPError),
    ],
)
def test_http_errors_do_not_leak_bodies_retry_or_fall_back(
    status: int, error_type: type[Exception]
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status, text="sentinel-secret", headers={"Location": "https://other.test/"}
        )

    with client(handler) as sdk, pytest.raises(error_type) as caught:
        sdk.projects.get(project_id="42")
    assert len(requests) == 1
    assert "sentinel-secret" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not-json", headers={"Content-Type": "application/json"}),
        httpx.Response(200, json=project(), headers={"Content-Type": "text/html"}),
        httpx.Response(200, json={**project(), "group_id": "9223372036854775808"}),
        httpx.Response(200, json={**project(), "extra": "sentinel-secret"}),
        httpx.Response(200, content=b"x" * 65537, headers={"Content-Type": "application/json"}),
    ],
)
def test_bad_response_is_sanitized(response: httpx.Response) -> None:
    with client(lambda _: response) as sdk, pytest.raises(ProtocolError) as caught:
        sdk.projects.get(project_id="42")
    assert caught.value.__context__ is None
    assert "sentinel-secret" not in str(caught.value)


@pytest.mark.parametrize(
    "patch",
    [
        {"offset": 1, "count": 3},
        {"has_more": False},
        {"cursor": ""},
    ],
)
def test_inconsistent_page_is_rejected(patch: dict[str, object]) -> None:
    with client(lambda _: httpx.Response(200, json={**page(), **patch})) as sdk:
        with pytest.raises(ProtocolError):
            sdk.projects.list(limit=1)


def test_duplicate_project_ids_are_rejected_within_page_limit() -> None:
    body = {
        **page(),
        "items": [summary(), summary()],
        "limit": 2,
        "count": 2,
        "has_more": False,
    }
    with client(lambda _: httpx.Response(200, json=body)) as sdk:
        with pytest.raises(ProtocolError):
            sdk.projects.list(limit=2)


@pytest.mark.parametrize(
    "arguments",
    [
        {"offset": 2**31},
        {"group_id": "9223372036854775808"},
        {"cursor": "bad\n"},
    ],
)
def test_invalid_input_never_sends_http(arguments: dict[str, Any]) -> None:
    def unexpected(_: httpx.Request) -> httpx.Response:
        pytest.fail("unexpected HTTP request")

    with client(unexpected) as sdk, pytest.raises(ConfigurationError):
        sdk.projects.list(**arguments)


def test_transport_error_is_redacted_and_client_close_is_preserved() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("sentinel-secret", request=request)

    sdk = client(handler)
    try:
        with pytest.raises(TransportError) as caught:
            sdk.projects.get(project_id="42")
        assert caught.value.__context__ is None
        assert "sentinel-secret" not in str(caught.value)
    finally:
        sdk.close()
    with pytest.raises(ConfigurationError, match="closed"):
        sdk.projects.get(project_id="42")
    assert calls == 1


def test_opt_in_only_changes_project_reads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/graphql/"
        body = json.loads(request.content)
        assert body["operationName"] == "UpdateProject"
        return httpx.Response(
            200,
            json={
                "data": {
                    "projects": {"updateProject": {"status": {"succeeded": True, "error": None}}}
                }
            },
        )

    with client(handler) as sdk:
        sdk.projects.update(project_id="42", name="Updated")


def test_unknown_project_read_mode_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        Client(api_key="test-key", project_reads="unknown")  # type: ignore[arg-type]


def test_oversized_encoded_route_raises_safe_configuration_error() -> None:
    def unexpected(_: httpx.Request) -> httpx.Response:
        pytest.fail("unexpected HTTP request")

    with client(unexpected) as sdk, pytest.raises(ConfigurationError) as caught:
        sdk.projects.get_by_route(route="/" + "日本" * 8191)
    assert caught.value.__context__ is None
    assert "日本" not in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [
        b'{"number":' + b"9" * 5000 + b"}",
        b'{"nested":' + b"[" * 3000 + b"0" + b"]" * 3000 + b"}",
    ],
)
def test_pathological_json_is_a_sanitized_protocol_error(body: bytes) -> None:
    with client(
        lambda _: httpx.Response(200, content=body, headers={"content-type": "application/json"})
    ) as sdk:
        with pytest.raises(ProtocolError) as caught:
            sdk.projects.get(project_id="42")
        assert caught.value.__context__ is None
