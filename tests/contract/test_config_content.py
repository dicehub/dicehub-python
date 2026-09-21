from __future__ import annotations

import io
import json

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    ConfigContentArea,
    ConfigContentEntry,
    ConfigContentPage,
    ConfigContentType,
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


def _default_response(field: str) -> dict[str, object]:
    return {
        "data": {
            "configs": {
                field: {"status": {"succeeded": True, "error": None}},
            }
        }
    }


def test_update_uses_fixed_metadata_mutation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "UpdateConfig"
        assert payload["variables"] == {
            "configId": "301",
            "name": "Renamed",
            "description": "Automation metadata",
        }
        assert "updateConfig" in payload["query"]
        return httpx.Response(200, json=_default_response("updateConfig"), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        client.configs.update(
            config_id="301",
            name="Renamed",
            description="Automation metadata",
        )


def test_list_content_uses_fixed_operation_and_returns_typed_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListConfigContent"
        assert payload["variables"] == {
            "configId": "301",
            "area": "TEXTS",
            "path": "boundary",
            "deep": True,
            "order": "DESC",
            "offset": 2.0,
            "limit": 10.0,
            "cursor": "cursor-value",
        }
        assert "entries { path resourceType }" in payload["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "configs": {
                        "listConfigContent": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 2.0, "count": 1.0, "cursor": "next"},
                            "entries": [
                                {
                                    "path": "boundary/inlet.yaml",
                                    "resourceType": "TEXT",
                                }
                            ],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        page = client.configs.list_content(
            config_id="301",
            area=ConfigContentArea.TEXTS,
            path="boundary",
            recursive=True,
            order=SortOrder.DESC,
            offset=2,
            limit=10,
            cursor="cursor-value",
        )

    assert page == ConfigContentPage(
        entries=(
            ConfigContentEntry(
                path="boundary/inlet.yaml",
                resource_type=ConfigContentType.TEXT,
            ),
        ),
        offset=2,
        count=1,
        cursor="next",
    )


def test_text_operations_use_fixed_documents() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        operation = payload["operationName"]
        response: dict[str, object]
        if operation == "GetConfigText":
            response = {
                "data": {
                    "configs": {
                        "getConfigText": {
                            "status": {"succeeded": True, "error": None},
                            "content": "value: 7\n",
                        }
                    }
                }
            }
        elif operation == "SetConfigText":
            response = _default_response("setConfigText")
        else:
            response = _default_response("deleteConfigContent")
        return httpx.Response(200, json=response, request=request)

    with _client(httpx.MockTransport(handler)) as client:
        assert client.configs.get_text(config_id="301", path="boundary/inlet.yaml") == "value: 7\n"
        client.configs.set_text(
            config_id="301",
            path="boundary/inlet.yaml",
            content="value: 8\r\n",
        )
        client.configs.delete_content(
            config_id="301",
            area=ConfigContentArea.TEXTS,
            path="boundary/inlet.yaml",
        )

    assert [request["operationName"] for request in requests] == [
        "GetConfigText",
        "SetConfigText",
        "DeleteConfigContent",
    ]
    assert requests[1]["variables"] == {
        "configId": "301",
        "path": "boundary/inlet.yaml",
        "content": "value: 8\n",
    }


def test_get_text_allows_valid_content_larger_than_the_default_envelope() -> None:
    content = "x" * (70 * 1024)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "configs": {
                        "getConfigText": {
                            "status": {"succeeded": True, "error": None},
                            "content": content,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client:
        assert client.configs.get_text(config_id="301", path="large.txt") == content


def test_get_text_keeps_its_larger_response_envelope_bounded() -> None:
    content = "x" * (13 * 1024 * 1024)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "configs": {
                        "getConfigText": {
                            "status": {"succeeded": True, "error": None},
                            "content": content,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.configs.get_text(config_id="301", path="too-large.txt")


def test_binary_upload_and_download_use_fixed_origin_streaming_routes() -> None:
    uploaded: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert request.url.raw_path == b"/api/v1/configs/301/files/mesh/input%20file.bin"
        if request.method == "PUT":
            assert request.headers["content-type"] == "application/octet-stream"
            uploaded.append(request.read())
            return httpx.Response(
                200,
                json={"status": {"succeeded": True, "error": None}},
                request=request,
            )
        return httpx.Response(
            200,
            content=b"downloaded-content",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    destination = io.BytesIO()
    with _client(httpx.MockTransport(handler)) as client:
        client.configs.upload_file(
            config_id="301",
            path="mesh/input file.bin",
            source=io.BytesIO(b"uploaded-content"),
        )
        count = client.configs.download_file(
            config_id="301",
            path="mesh/input file.bin",
            destination=destination,
        )

    assert uploaded == [b"uploaded-content"]
    assert count == len(b"downloaded-content")
    assert destination.getvalue() == b"downloaded-content"


def test_download_maps_rest_status_without_writing_server_body() -> None:
    response = {
        "status": {
            "succeeded": False,
            "error": "PERMISSIONS_ERROR",
            "message": "sentinel server detail",
        }
    }
    destination = io.BytesIO()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.configs.download_file(
            config_id="301",
            path="mesh/file.bin",
            destination=destination,
        )

    assert captured.value.server_code == "PERMISSIONS_ERROR"
    assert "sentinel" not in str(captured.value)
    assert destination.getvalue() == b""


def test_download_enforces_configured_response_limit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"1234",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.configs.download_file(
            config_id="301",
            path="mesh/file.bin",
            destination=io.BytesIO(),
            max_bytes=3,
        )


@pytest.mark.parametrize("failure", ["transport", "http", "protocol"])
def test_upload_ambiguity_is_non_retryable_and_not_retried(failure: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("sentinel transport detail", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel body", request=request)
        return httpx.Response(200, text="not-json", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.configs.upload_file(
            config_id="301",
            path="mesh/file.bin",
            source=io.BytesIO(b"content"),
        )

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
