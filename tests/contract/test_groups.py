from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    Group,
    GroupDetail,
    GroupOrderField,
    GroupPage,
    GroupVisibility,
    MutationOutcomeUnknownError,
    ProtocolError,
    SortOrder,
)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _group(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "groupId": "73",
        "parentId": "42",
        "name": "Research",
        "displayRoute": "dicehub / Research",
        "route": "/dicehub/research",
        "visibility": "PRIVATE",
        "hasChildren": True,
    }
    payload.update(overrides)
    return payload


def _group_detail(**overrides: object) -> dict[str, object]:
    payload = _group(
        description="Simulation research group.",
        avatarUrl="https://dicehub.test/api/v1/groups/73/avatar",
    )
    payload.update(overrides)
    return payload


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    groups: object = ...,
) -> dict[str, object]:
    if info is ...:
        info = {"offset": 2.0, "count": 1.0, "cursor": "next-cursor"}
    if groups is ...:
        groups = [_group()]
    return {
        "data": {
            "groups": {
                "listGroups": {
                    "status": status or _status(),
                    "info": info,
                    "groups": groups,
                }
            }
        }
    }


def _single_response(
    field: str,
    *,
    group: object = ...,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    if group is ...:
        group = _group_detail()
    return {
        "data": {
            "groups": {
                field: {
                    "status": status or _status(),
                    "group": group,
                }
            }
        }
    }


def _default_response(
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "data": {
            "groups": {
                "updateGroup": {
                    "status": status or _status(),
                }
            }
        }
    }


def _expected_group() -> Group:
    return Group(
        group_id="73",
        parent_id="42",
        name="Research",
        display_route="dicehub / Research",
        route="/dicehub/research",
        visibility=GroupVisibility.PRIVATE,
        has_children=True,
    )


def _expected_group_detail() -> GroupDetail:
    return GroupDetail(
        **_expected_group().model_dump(),
        description="Simulation research group.",
        avatar_url="https://dicehub.test/api/v1/groups/73/avatar",
    )


def test_list_uses_fixed_variables_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListGroups"
        assert payload["variables"] == {
            "userId": "7",
            "parentId": "42",
            "searchFilter": "research",
            "orderBy": "updated_at",
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
        }
        query = payload["query"]
        assert "listGroups" in query
        assert "$searchFilter: String" in query
        assert "research" not in query
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.groups.list(
            user_id="7",
            parent_id="42",
            search_filter="research",
            order_by=GroupOrderField.UPDATED_AT,
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == GroupPage(
        groups=(_expected_group(),),
        offset=2,
        count=1,
        cursor="next-cursor",
    )


def test_list_uses_bounded_defaults() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"] == {
            "userId": None,
            "parentId": None,
            "searchFilter": None,
            "orderBy": "name",
            "order": "ASC",
            "offset": 0.0,
            "limit": 20.0,
            "cursor": None,
        }
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.groups.list()


@pytest.mark.parametrize(
    ("method", "argument", "operation_name", "field", "variables"),
    [
        ("get", {"group_id": "73"}, "GetGroup", "getGroupById", {"groupId": "73"}),
        (
            "get_by_route",
            {"route": "/dicehub/research"},
            "GetGroupByRoute",
            "getGroupByRoute",
            {"route": "/dicehub/research"},
        ),
    ],
)
def test_get_operations_use_fixed_variables_and_return_group(
    method: str,
    argument: dict[str, str],
    operation_name: str,
    field: str,
    variables: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert field in payload["query"]
        assert str(next(iter(variables.values()))) not in payload["query"]
        if method == "get_by_route":
            assert payload["query"].index("      group {") < payload["query"].index(
                "      status {"
            )
        return httpx.Response(200, json=_single_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        group = getattr(client.groups, method)(**argument)

    assert group == _expected_group_detail()


def test_update_uses_fixed_variables_with_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "UpdateGroup"
        assert payload["variables"] == {
            "groupId": "73",
            "name": "Applied Research",
            "slug": "applied-research",
            "description": "Updated by automation",
            "visibility": "INTERNAL",
        }
        query = payload["query"]
        assert "updateGroup" in query
        assert "Applied Research" not in query
        assert "test-api-key" not in query
        return httpx.Response(200, json=_default_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.groups.update(
            group_id="73",
            name="Applied Research",
            slug="applied-research",
            description="Updated by automation",
            visibility=GroupVisibility.INTERNAL,
        )


def test_update_can_clear_description() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"] == {
            "groupId": "73",
            "name": None,
            "slug": None,
            "description": "",
            "visibility": None,
        }
        return httpx.Response(200, json=_default_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.groups.update(group_id="73", description="")


@pytest.mark.parametrize("operation", ["list", "get", "get_by_route"])
@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_status_failures_are_generic(
    operation: str,
    server_error: str,
    error_type: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if operation == "list":
            response = _list_response(
                status=_status(succeeded=False, error=server_error),
                info=None,
                groups=None,
            )
        else:
            field = "getGroupById" if operation == "get" else "getGroupByRoute"
            response = _single_response(
                field,
                group=None,
                status=_status(succeeded=False, error=server_error),
            )
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(error_type) as captured:
        if operation == "list":
            client.groups.list()
        elif operation == "get":
            client.groups.get(group_id="73")
        else:
            client.groups.get_by_route(route="/dicehub/missing")

    assert server_error not in str(captured.value)


@pytest.mark.parametrize(
    "response",
    [
        _list_response(info=None),
        _list_response(groups=None),
        _list_response(info={"offset": 0.5, "count": 1.0, "cursor": "next"}),
        _list_response(groups=[_group(groupId="01")]),
        _list_response(groups=[_group(parentId="invalid")]),
        _list_response(groups=[_group(hasChildren=None)]),
        _list_response(groups=[_group(hasChildren=1)]),
        _list_response(groups=[_group(secret="must-not-be-accepted")]),
    ],
)
def test_malformed_list_response_fails_closed(response: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )
    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.groups.list()

    assert "must-not-be-accepted" not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize("operation", ["get", "get_by_route"])
def test_success_without_group_fails_closed(operation: str) -> None:
    field = "getGroupById" if operation == "get" else "getGroupByRoute"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_single_response(field, group=None),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        if operation == "get":
            client.groups.get(group_id="73")
        else:
            client.groups.get_by_route(route="/dicehub/missing")


@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_update_status_failures_are_generic(
    server_error: str,
    error_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_default_response(
                status=_status(succeeded=False, error=server_error),
            ),
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(error_type) as captured:
        client.groups.update(group_id="73", name="Updated group")

    assert server_error not in str(captured.value)


@pytest.mark.parametrize("failure", ["transport", "http", "graphql", "protocol"])
def test_update_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("sentinel transport details", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel body", request=request)
        if failure == "graphql":
            return httpx.Response(
                200,
                json={"errors": [{"message": "sentinel GraphQL details"}]},
                request=request,
            )
        return httpx.Response(200, json={"data": {"groups": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.groups.update(group_id="73", name="Updated group")

    assert request_count == 1
    assert captured.value.code == "MUTATION_OUTCOME_UNKNOWN"
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None
