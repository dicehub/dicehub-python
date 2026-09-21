from __future__ import annotations

import io
import json
from typing import Any, BinaryIO, cast

import httpx
import pytest
from pydantic import SecretStr

from dicehub import (
    APIError,
    Client,
    ConfigurationError,
    MutationOutcomeUnknownError,
    ProtocolError,
    RunResultS3Credentials,
    TransportError,
)

RUN_ID = "12345678-1234-5678-9234-567812345678"
RESOURCE_ID = "87654321-4321-4765-8765-876543210987"
ACCESS_KEY_ID = "A" * 20
SECRET_ACCESS_KEY = "B" * 40


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def test_download_results_streams_one_fixed_archive_route() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.method == "GET"
        assert request.url.raw_path == f"/api/v1/run/archive/result/{RUN_ID}".encode()
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert "application/octet-stream" in request.headers["accept"]
        return httpx.Response(
            200,
            content=b"PK\x03\x04archive-content",
            headers={
                "Content-Type": "application/zip",
                "Content-Disposition": 'attachment; filename="../../outside.zip"',
            },
            request=request,
        )

    destination = io.BytesIO()
    with _client(httpx.MockTransport(handler)) as client:
        count = client.runs.download_results(
            run_id=RUN_ID.upper(),
            destination=destination,
        )

    assert calls == 1
    assert count == len(b"PK\x03\x04archive-content")
    assert destination.getvalue() == b"PK\x03\x04archive-content"


def test_download_results_maps_rest_error_without_writing_or_leaking_body() -> None:
    destination = io.BytesIO()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": {
                    "succeeded": False,
                    "error": "PERMISSIONS_ERROR",
                    "message": "sentinel server detail",
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(APIError) as captured:
        client.runs.download_results(run_id=RUN_ID, destination=destination)

    assert captured.value.server_code == "PERMISSIONS_ERROR"
    assert "sentinel" not in str(captured.value)
    assert destination.getvalue() == b""


def test_download_results_rejects_non_zip_success_without_writing() -> None:
    destination = io.BytesIO()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html>proxy response</html>",
            headers={"Content-Type": "text/html"},
            request=request,
        )

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(
            ProtocolError,
            match="invalid run result archive content type",
        ),
    ):
        client.runs.download_results(run_id=RUN_ID, destination=destination)

    assert destination.getvalue() == b""


def test_download_results_is_bounded_and_never_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            content=b"1234",
            headers={"Content-Type": "application/zip"},
            request=request,
        )

    destination = io.BytesIO()
    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError) as captured:
        client.runs.download_results(
            run_id=RUN_ID,
            destination=destination,
            max_bytes=3,
        )

    assert calls == 1
    assert "run result archive" in str(captured.value)
    assert destination.getvalue() == b""


def test_download_results_transport_failure_is_redacted_and_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadError("test-api-key sentinel response", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(TransportError) as captured,
    ):
        client.runs.download_results(run_id=RUN_ID, destination=io.BytesIO())

    assert calls == 1
    assert "test-api-key" not in str(captured.value)
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    ("run_id", "max_bytes"),
    [
        ("../../outside", 1),
        (RUN_ID, 0),
        (RUN_ID, True),
        (RUN_ID, 2 * 1024 * 1024 * 1024 + 1),
    ],
)
def test_download_results_rejects_invalid_path_inputs_before_request(
    run_id: str,
    max_bytes: Any,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.runs.download_results(
            run_id=run_id,
            destination=io.BytesIO(),
            max_bytes=max_bytes,
        )

    assert calls == 0


def test_download_results_requires_binary_destination_with_complete_writes() -> None:
    class PartialDestination:
        def write(self, content: bytes) -> int:
            return len(content) - 1

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"archive",
            headers={"Content-Type": "application/zip"},
            request=request,
        )
    )
    with _client(transport) as client, pytest.raises(ProtocolError, match="partial write"):
        client.runs.download_results(
            run_id=RUN_ID,
            destination=cast(BinaryIO, PartialDestination()),
        )

    with _client(transport) as client, pytest.raises(ConfigurationError, match="writable"):
        client.runs.download_results(
            run_id=RUN_ID,
            destination=cast(BinaryIO, object()),
        )


@pytest.mark.parametrize("regenerate", [False, True])
def test_get_result_s3_credentials_uses_results_panel_operations(
    regenerate: bool,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-api-key"
        if calls == 1:
            assert payload["operationName"] == "GetRunResultFolder"
            assert payload["variables"] == {
                "appId": "42",
                "key": f"data/run/{RUN_ID}/result",
            }
            assert "getResourceByKey" in payload["query"]
            response = {
                "data": {
                    "resources": {
                        "getResourceByKey": {
                            "status": {"succeeded": True, "error": None},
                            "resource": {"resourceId": RESOURCE_ID},
                        }
                    }
                }
            }
        else:
            assert payload["operationName"] == "GetRunResultS3Credentials"
            assert payload["variables"] == {
                "resourceId": RESOURCE_ID,
                "generateNewKey": regenerate,
            }
            assert "getFolderS3Credentials" in payload["query"]
            response = {
                "data": {
                    "resources": {
                        "getFolderS3Credentials": {
                            "status": {"succeeded": True, "error": None},
                            "bucket": RESOURCE_ID,
                            "accessKeyId": ACCESS_KEY_ID,
                            "secretAccessKey": SECRET_ACCESS_KEY,
                        }
                    }
                }
            }
        return httpx.Response(200, json=response, request=request)

    kwargs = {"regenerate": True} if regenerate else {}
    with _client(httpx.MockTransport(handler)) as client:
        credentials = client.runs.get_result_s3_credentials(
            app_id="42",
            run_id=RUN_ID.upper(),
            **kwargs,
        )

    assert calls == 2
    assert credentials == RunResultS3Credentials(
        bucket=RESOURCE_ID,
        access_key_id=SecretStr(ACCESS_KEY_ID),
        secret_access_key=SecretStr(SECRET_ACCESS_KEY),
    )
    assert credentials.access_key_id.get_secret_value() == ACCESS_KEY_ID
    assert credentials.secret_access_key.get_secret_value() == SECRET_ACCESS_KEY
    assert ACCESS_KEY_ID not in repr(credentials)
    assert SECRET_ACCESS_KEY not in credentials.model_dump_json()


def test_get_result_s3_credentials_maps_mutation_failure_without_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "resources": {
                            "getResourceByKey": {
                                "status": {"succeeded": True, "error": None},
                                "resource": {"resourceId": RESOURCE_ID},
                            }
                        }
                    }
                },
                request=request,
            )
        raise httpx.ReadError(f"{SECRET_ACCESS_KEY} response", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.runs.get_result_s3_credentials(app_id="42", run_id=RUN_ID)

    assert calls == 2
    assert captured.value.retryable is False
    assert SECRET_ACCESS_KEY not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"app_id": "0", "run_id": RUN_ID},
        {"app_id": "42", "run_id": "not-a-run-id"},
        {"app_id": "42", "run_id": RUN_ID, "regenerate": 1},
    ],
)
def test_get_result_s3_credentials_rejects_invalid_inputs_before_request(
    kwargs: dict[str, Any],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("invalid input reached the transport")

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.runs.get_result_s3_credentials(**kwargs)
