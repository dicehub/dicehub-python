from __future__ import annotations

import json

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    MutationOutcomeUnknownError,
    ProtocolError,
    Resource,
    ResourcePage,
    ResourceType,
    SortOrder,
)

NAMESPACE_ID = "101"
RESOURCE_ID = "12345678-1234-5678-9234-567812345678"


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


def _resource(
    *,
    resource_id: str = RESOURCE_ID,
    key: str = "data/config/controlDict",
    resource_type: str = "TEXT",
) -> dict[str, object]:
    return {
        "resourceId": resource_id,
        "namespaceId": NAMESPACE_ID,
        "key": key,
        "resourceType": resource_type,
    }


def _list_response(
    *,
    status: dict[str, object] | None = None,
    info: object = ...,
    resources: object = ...,
) -> dict[str, object]:
    return {
        "data": {
            "resources": {
                "listResources": {
                    "status": status or _status(),
                    "info": (
                        {"offset": 2.0, "count": 1.0, "cursor": "next-cursor"}
                        if info is ...
                        else info
                    ),
                    "resources": [_resource()] if resources is ... else resources,
                }
            }
        }
    }


def _single_response(
    field: str,
    *,
    status: dict[str, object] | None = None,
    resource: object = ...,
) -> dict[str, object]:
    return {
        "data": {
            "resources": {
                field: {
                    "status": status or _status(),
                    "resource": _resource() if resource is ... else resource,
                }
            }
        }
    }


def _mutation_response(
    field: str,
    *,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    return {"data": {"resources": {field: {"status": status or _status()}}}}


def test_list_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert payload["operationName"] == "ListResources"
        assert payload["variables"] == {
            "namespaceId": NAMESPACE_ID,
            "path": "data/config",
            "resourceType": "FILE",
            "searchFilter": None,
            "deep": True,
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
        }
        assert "listResources" in payload["query"]
        assert "resourceId" in payload["query"]
        assert "namespaceId" in payload["query"]
        assert "key" in payload["query"]
        assert "resourceType" in payload["query"]
        assert NAMESPACE_ID not in payload["query"]
        assert "test-api-key" not in payload["query"]
        return httpx.Response(200, json=_list_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        page = client.resources.list(
            namespace_id=NAMESPACE_ID,
            path="config",
            resource_type=ResourceType.FILE,
            recursive=True,
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == ResourcePage(
        resources=(
            Resource(
                resource_id=RESOURCE_ID,
                namespace_id=NAMESPACE_ID,
                key="data/config/controlDict",
                resource_type=ResourceType.TEXT,
            ),
        ),
        offset=2,
        count=1,
        cursor="next-cursor",
    )


@pytest.mark.parametrize(
    ("method", "arguments", "operation_name", "field", "variables"),
    [
        (
            "get",
            {"resource_id": RESOURCE_ID},
            "GetResource",
            "getResourceById",
            {"resourceId": RESOURCE_ID},
        ),
        (
            "get_by_key",
            {"namespace_id": NAMESPACE_ID, "path": "config/controlDict"},
            "GetResourceByKey",
            "getResourceByKey",
            {"namespaceId": NAMESPACE_ID, "key": "data/config/controlDict"},
        ),
    ],
)
def test_get_operations_use_fixed_documents_and_variables(
    method: str,
    arguments: dict[str, str],
    operation_name: str,
    field: str,
    variables: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == operation_name
        assert payload["variables"] == variables
        assert field in payload["query"]
        assert RESOURCE_ID not in payload["query"]
        return httpx.Response(200, json=_single_response(field), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        resource = getattr(client.resources, method)(**arguments)

    assert resource == Resource(
        resource_id=RESOURCE_ID,
        namespace_id=NAMESPACE_ID,
        key="data/config/controlDict",
        resource_type=ResourceType.TEXT,
    )


def test_text_reads_and_writes_use_fixed_operations_and_normalize_newlines() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        operation = payload["operationName"]
        response: dict[str, object]
        if operation == "GetResourceText":
            response = {
                "data": {
                    "resources": {
                        "getTextContent": {
                            "status": _status(),
                            "content": "value: 7\n",
                        }
                    }
                }
            }
        elif operation == "CreateResourceText":
            response = _mutation_response("createText")
        else:
            response = _mutation_response("setTextContent")
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client:
        assert client.resources.get_text(resource_id=RESOURCE_ID) == "value: 7\n"
        client.resources.create_text(
            namespace_id=NAMESPACE_ID,
            path="config/controlDict",
            content="value: 8\r\n",
        )
        client.resources.set_text(resource_id=RESOURCE_ID, content="value: 9\r\n")

    assert [request["operationName"] for request in requests] == [
        "GetResourceText",
        "CreateResourceText",
        "SetResourceText",
    ]
    assert requests[0]["variables"] == {"resourceId": RESOURCE_ID}
    assert requests[1]["variables"] == {
        "namespaceId": NAMESPACE_ID,
        "key": "data/config/controlDict",
        "content": "value: 8\n",
    }
    assert requests[2]["variables"] == {
        "resourceId": RESOURCE_ID,
        "content": "value: 9\n",
    }


def test_delete_uses_exact_resource_id_without_follow_up_read() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["operationName"] == "DeleteResource"
        assert payload["variables"] == {"resourceId": RESOURCE_ID}
        assert "deleteResource(resourceId: $resourceId)" in payload["query"]
        assert RESOURCE_ID not in payload["query"]
        return httpx.Response(200, json=_mutation_response("deleteResource"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.resources.delete(resource_id=RESOURCE_ID)

    assert len(requests) == 1


@pytest.mark.parametrize(
    ("method", "failure"),
    [
        ("create_text", "transport"),
        ("create_text", "http"),
        ("create_text", "graphql"),
        ("create_text", "protocol"),
        ("set_text", "transport"),
        ("set_text", "protocol"),
        ("delete", "transport"),
        ("delete", "protocol"),
    ],
)
def test_mutations_map_ambiguous_failures_without_retry(method: str, failure: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("sentinel transport details", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel response", request=request)
        if failure == "graphql":
            return httpx.Response(
                200,
                json={"errors": [{"message": "sentinel GraphQL details"}]},
                request=request,
            )
        return httpx.Response(200, json={"data": {"resources": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        if method == "create_text":
            client.resources.create_text(
                namespace_id=NAMESPACE_ID,
                path="config/controlDict",
                content="value: 1\n",
            )
        elif method == "set_text":
            client.resources.set_text(resource_id=RESOURCE_ID, content="value: 1\n")
        else:
            client.resources.delete(resource_id=RESOURCE_ID)

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("operation", "response"),
    [
        (
            "list",
            _list_response(status=_status(succeeded=False, error="PERMISSIONS_ERROR")),
        ),
        (
            "get",
            _single_response(
                "getResourceById",
                status=_status(succeeded=False, error="PERMISSIONS_ERROR"),
            ),
        ),
    ],
)
def test_queries_map_failed_status_without_server_details(
    operation: str,
    response: dict[str, object],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        if operation == "list":
            client.resources.list(namespace_id=NAMESPACE_ID)
        else:
            client.resources.get(resource_id=RESOURCE_ID)

    assert captured.value.message == "dicehub rejected the operation."
    assert "PERMISSIONS_ERROR" not in str(captured.value)


@pytest.mark.parametrize(
    ("method", "response"),
    [
        ("list", _list_response(info=None, resources=[])),
        (
            "list",
            _list_response(
                info={"offset": 0.5, "count": 1.0, "cursor": "cursor"},
                resources=[],
            ),
        ),
        (
            "list",
            _list_response(resources=[{**_resource(), "resourceType": "UNKNOWN"}]),
        ),
        ("get", _single_response("getResourceById", resource=None)),
        ("get", {"data": {"resources": {"unexpected": {}}}}),
    ],
)
def test_successful_but_malformed_resource_payload_is_rejected(
    method: str,
    response: dict[str, object],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        if method == "list":
            client.resources.list(namespace_id=NAMESPACE_ID)
        else:
            client.resources.get(resource_id=RESOURCE_ID)

    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_get_text_rejects_non_text_content_payload() -> None:
    response = {
        "data": {
            "resources": {
                "getTextContent": {
                    "status": _status(),
                    "content": None,
                }
            }
        }
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.resources.get_text(resource_id=RESOURCE_ID)


def test_resource_model_is_strict_and_immutable() -> None:
    resource = Resource(
        resource_id=RESOURCE_ID,
        namespace_id=NAMESPACE_ID,
        key="data/file.bin",
        resource_type=ResourceType.FILE,
    )

    with pytest.raises((TypeError, ValueError)):
        resource.key = "data/other.bin"


def test_resource_page_rejects_extra_fields() -> None:
    with pytest.raises((TypeError, ValueError)):
        ResourcePage(
            resources=(),
            offset=0,
            count=0,
            cursor="",
            unexpected="must be rejected",  # type: ignore[call-arg]
        )


def test_resource_constants_cover_server_enum() -> None:
    assert [resource_type.value for resource_type in ResourceType] == [
        "FOLDER",
        "TEXT",
        "FILE",
        "CHANNEL",
    ]
