from __future__ import annotations

import base64
import io
import json

import httpx
import pytest

from dicehub import (
    Client,
    ConfigurationError,
    GroupDetail,
    GroupVisibility,
    MutationOutcomeUnknownError,
)


def _api_key_client(transport: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    )


def _session_client(transport: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-cookie",
        transport=transport,
    )


def _status() -> dict[str, object]:
    return {"succeeded": True, "error": None}


def _created_group(*, parent_id: str | None) -> dict[str, object]:
    route = "/automation" if parent_id is None else "/research/automation"
    return {
        "groupId": "73",
        "parentId": parent_id,
        "name": "Automation",
        "displayRoute": route,
        "route": route,
        "visibility": "PRIVATE",
        "hasChildren": None,
        "description": "Managed by the SDK",
        "avatarUrl": None,
    }


def _create_response(*, parent_id: str | None, group: object = ...) -> dict[str, object]:
    if group is ...:
        group = _created_group(parent_id=parent_id)
    return {
        "data": {
            "groups": {
                "createGroup": {
                    "status": _status(),
                    "group": group,
                }
            }
        }
    }


def _mutation_response(field: str) -> dict[str, object]:
    return {"data": {"groups": {field: {"status": _status()}}}}


def _assert_created_group(group: GroupDetail, *, parent_id: str | None) -> None:
    assert group == GroupDetail(
        group_id="73",
        parent_id=parent_id,
        name="Automation",
        display_route="/automation" if parent_id is None else "/research/automation",
        route="/automation" if parent_id is None else "/research/automation",
        visibility=GroupVisibility.PRIVATE,
        has_children=False,
        description="Managed by the SDK",
        avatar_url=None,
    )


def test_create_subgroup_uses_api_key_and_fixed_variables() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "CreateGroup"
        assert payload["variables"] == {
            "name": "Automation",
            "slug": "automation",
            "description": "Managed by the SDK",
            "groupId": "42",
            "visibility": "PRIVATE",
        }
        assert "automation" not in payload["query"].lower()
        return httpx.Response(
            200,
            json=_create_response(parent_id="42"),
            request=request,
        )

    with _api_key_client(httpx.MockTransport(handler)) as client:
        group = client.groups.create(
            name="Automation",
            slug="automation",
            parent_id="42",
            description="Managed by the SDK",
        )

    _assert_created_group(group, parent_id="42")


def test_create_top_level_group_uses_session_cookie() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["cookie"] == "_dicehub_session=test-session-cookie"
        assert "authorization" not in request.headers
        assert payload["variables"]["groupId"] is None
        return httpx.Response(
            200,
            json=_create_response(parent_id=None),
            request=request,
        )

    with _session_client(httpx.MockTransport(handler)) as client:
        group = client.groups.create(
            name="Automation",
            slug="automation",
            description="Managed by the SDK",
        )

    _assert_created_group(group, parent_id=None)


def test_top_level_create_with_api_key_fails_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _api_key_client(httpx.MockTransport(handler)) as client,
        pytest.raises(
            ConfigurationError,
            match="requires session-cookie authentication",
        ),
    ):
        client.groups.create(name="Automation", slug="automation")

    assert request_count == 0


def test_delete_group_uses_api_key_and_exact_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "DeleteGroup"
        assert payload["variables"] == {"groupId": "73"}
        assert "73" not in payload["query"]
        return httpx.Response(200, json=_mutation_response("deleteGroup"), request=request)

    with _api_key_client(httpx.MockTransport(handler)) as client:
        client.groups.delete(group_id="73")


def test_move_group_is_session_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["cookie"] == "_dicehub_session=test-session-cookie"
        assert payload["operationName"] == "MoveGroup"
        assert payload["variables"] == {"groupId": "73", "toGroupId": "42"}
        return httpx.Response(200, json=_mutation_response("moveGroup"), request=request)

    with _session_client(httpx.MockTransport(handler)) as client:
        client.groups.move(group_id="73", to_group_id="42")

    request_count = 0

    def rejected_handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _api_key_client(httpx.MockTransport(rejected_handler)) as client,
        pytest.raises(
            ConfigurationError,
            match="requires session-cookie authentication",
        ),
    ):
        client.groups.move(group_id="73", to_group_id="42")

    assert request_count == 0


def test_set_and_clear_avatar_use_bounded_base64_variables() -> None:
    image = b"\x89PNG\r\n\x1a\n" + b"bounded-image"
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "UpdateGroupAvatar"
        assert payload["variables"]["groupId"] == "73"
        expected_avatar = (
            f"data:image/png;base64,{base64.b64encode(image).decode('ascii')}" if calls == 1 else ""
        )
        assert payload["variables"]["avatar"] == expected_avatar
        if expected_avatar:
            assert expected_avatar not in payload["query"]
        return httpx.Response(200, json=_mutation_response("updateGroup"), request=request)

    with _api_key_client(httpx.MockTransport(handler)) as client:
        client.groups.set_avatar(group_id="73", source=io.BytesIO(image))
        client.groups.clear_avatar(group_id="73")

    assert calls == 2


def test_successful_create_without_group_has_unknown_outcome() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_create_response(parent_id="42", group=None),
            request=request,
        )
    )

    with _api_key_client(transport) as client, pytest.raises(MutationOutcomeUnknownError):
        client.groups.create(name="Automation", slug="automation", parent_id="42")


@pytest.mark.parametrize("operation", ["create", "avatar", "delete", "move"])
def test_lifecycle_mutations_are_not_retried_after_transport_failure(operation: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        raise httpx.ConnectError("sentinel transport details", request=request)

    transport = httpx.MockTransport(handler)
    client_factory = _session_client if operation == "move" else _api_key_client
    with (
        client_factory(transport) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        if operation == "create":
            client.groups.create(name="Automation", slug="automation", parent_id="42")
        elif operation == "avatar":
            client.groups.clear_avatar(group_id="73")
        elif operation == "delete":
            client.groups.delete(group_id="73")
        else:
            client.groups.move(group_id="73", to_group_id="42")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
