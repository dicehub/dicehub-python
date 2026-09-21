from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import BinaryIO, cast

import httpx
import pytest

from dicehub import (
    APIError,
    Client,
    ConfigurationError,
    DownloadReceipt,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
    UploadReceipt,
)

NAMESPACE_ID = "101"
STORAGE_PATH = "config/input file.bin"
CONTENT = b"storage content\x00\xff"


def _client(handler: httpx.BaseTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


def _success_response() -> dict[str, object]:
    return {"status": {"succeeded": True, "error": None}}


class _TrackingSource:
    def __init__(self, content: bytes) -> None:
        self._stream = io.BytesIO(content)
        self.read_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        return self._stream.read(size)


class _PartialDestination:
    def __init__(self) -> None:
        self.content = bytearray()

    def write(self, content: bytes) -> int:
        self.content.extend(content[:-1])
        return len(content) - 1


class _IncrementalUploadTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.received = bytearray()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for chunk in cast(httpx.SyncByteStream, request.stream):
            self.received.extend(chunk)
        return httpx.Response(200, json=_success_response(), request=request)


def test_upload_stream_uses_fixed_same_origin_post_and_local_hash() -> None:
    content = b"x" * (64 * 1024 + 9)
    source = _TrackingSource(content)
    uploaded: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://dicehub.test/api/v1/storage/101/config/input%20file.bin"
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert request.headers["content-type"] == "application/octet-stream"
        uploaded.append(request.read())
        return httpx.Response(200, json=_success_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        receipt = client.storage.upload(
            namespace_id=NAMESPACE_ID,
            path=STORAGE_PATH,
            source=cast(BinaryIO, source),
        )

    assert uploaded == [content]
    assert source.read_sizes
    assert all(size == 64 * 1024 for size in source.read_sizes)
    assert receipt == UploadReceipt(
        namespace_id=NAMESPACE_ID,
        path=STORAGE_PATH,
        bytes_sent=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        server_verified=False,
    )


def test_upload_file_wraps_a_path_and_returns_a_local_receipt(tmp_path: Path) -> None:
    source_path = tmp_path / "source.bin"
    source_path.write_bytes(CONTENT)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.raw_path == b"/api/v1/storage/101/source.bin"
        assert request.read() == CONTENT
        return httpx.Response(200, json=_success_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client:
        receipt = client.storage.upload_file(
            namespace_id=NAMESPACE_ID,
            path="source.bin",
            source_path=source_path,
        )

    assert len(requests) == 1
    assert receipt.namespace_id == NAMESPACE_ID
    assert receipt.path == "source.bin"
    assert receipt.bytes_sent == len(CONTENT)
    assert receipt.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert receipt.server_verified is False


def test_upload_rejects_a_stream_that_exceeds_the_limit_before_completion() -> None:
    content = b"0123456789"
    source = _TrackingSource(content)
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        request.read()
        return httpx.Response(200, json=_success_response(), request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.storage.upload(
            namespace_id=NAMESPACE_ID,
            path="bounded.bin",
            source=cast(BinaryIO, source),
            max_bytes=len(content) - 1,
        )

    assert requests == 0
    assert source.read_sizes == [64 * 1024]


def test_upload_reports_unknown_outcome_after_a_prefix_was_consumed() -> None:
    chunk_bytes = 64 * 1024
    source = _TrackingSource(b"x" * (chunk_bytes + 1))
    transport = _IncrementalUploadTransport()

    with (
        _client(transport) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.storage.upload(
            namespace_id=NAMESPACE_ID,
            path="bounded.bin",
            source=cast(BinaryIO, source),
            max_bytes=chunk_bytes,
        )

    assert transport.received == b"x" * chunk_bytes
    assert source.read_sizes == [chunk_bytes, chunk_bytes]
    assert captured.value.retryable is False
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_download_stream_uses_fixed_same_origin_get_and_local_hash() -> None:
    destination = io.BytesIO()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "https://dicehub.test/api/v1/storage/101/config/input%20file.bin"
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert "application/octet-stream" in request.headers["accept"]
        return httpx.Response(
            200,
            content=CONTENT,
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        receipt = client.storage.download(
            namespace_id=NAMESPACE_ID,
            path=STORAGE_PATH,
            destination=destination,
        )

    assert destination.getvalue() == CONTENT
    assert receipt == DownloadReceipt(
        namespace_id=NAMESPACE_ID,
        path=STORAGE_PATH,
        bytes_received=len(CONTENT),
        sha256=hashlib.sha256(CONTENT).hexdigest(),
        server_verified=False,
    )


def test_download_file_is_atomic_and_replaces_the_destination(tmp_path: Path) -> None:
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"old content")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.raw_path == b"/api/v1/storage/101/download.bin"
        return httpx.Response(
            200,
            content=CONTENT,
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        receipt = client.storage.download_file(
            namespace_id=NAMESPACE_ID,
            path="download.bin",
            destination_path=destination,
            overwrite=True,
        )

    assert destination.read_bytes() == CONTENT
    assert receipt.namespace_id == NAMESPACE_ID
    assert receipt.path == "download.bin"
    assert receipt.bytes_received == len(CONTENT)
    assert receipt.sha256 == hashlib.sha256(CONTENT).hexdigest()
    assert receipt.server_verified is False
    assert list(tmp_path.glob(f".{destination.name}.*")) == []


def test_download_file_keeps_existing_destination_when_validation_fails(tmp_path: Path) -> None:
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"keep this content")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"too large",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        client.storage.download_file(
            namespace_id=NAMESPACE_ID,
            path="download.bin",
            destination_path=destination,
            overwrite=True,
            max_bytes=3,
        )

    assert destination.read_bytes() == b"keep this content"
    assert list(tmp_path.glob(f".{destination.name}.*")) == []


def test_download_file_keeps_existing_destination_when_response_is_truncated(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "download.bin"
    destination.write_bytes(b"keep this content")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"short",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": "9",
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        client.storage.download_file(
            namespace_id=NAMESPACE_ID,
            path="download.bin",
            destination_path=destination,
            overwrite=True,
        )

    assert destination.read_bytes() == b"keep this content"
    assert list(tmp_path.glob(f".{destination.name}.*")) == []


def test_download_is_bounded_and_does_not_write_an_oversized_chunk() -> None:
    destination = io.BytesIO()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            content=b"1234",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ProtocolError):
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="bounded.bin",
            destination=destination,
            max_bytes=3,
        )

    assert calls == 1
    assert destination.getvalue() == b""


def test_download_rejects_partial_destination_writes() -> None:
    destination = _PartialDestination()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"content",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError, match="partial write"):
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="partial.bin",
            destination=cast(BinaryIO, destination),
        )

    assert destination.content == b"conten"


def test_download_maps_json_error_without_writing_server_body() -> None:
    destination = io.BytesIO()
    response = {
        "status": {
            "succeeded": False,
            "error": "PERMISSIONS_ERROR",
            "message": "sentinel server detail",
        }
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with _client(transport) as client, pytest.raises(APIError) as captured:
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="protected.bin",
            destination=destination,
        )

    assert captured.value.server_code == "PERMISSIONS_ERROR"
    assert "sentinel" not in str(captured.value)
    assert destination.getvalue() == b""


def test_download_rejects_malformed_content_length_without_writing() -> None:
    destination = io.BytesIO()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"content",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": "not-a-length",
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="malformed.bin",
            destination=destination,
        )

    assert destination.getvalue() == b""


def test_storage_does_not_follow_cross_origin_redirects() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": "https://attacker.example/capture"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(HTTPError):
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="redirect.bin",
            destination=io.BytesIO(),
        )

    assert len(requests) == 1


@pytest.mark.parametrize("failure", ["transport", "http", "protocol"])
def test_upload_ambiguity_is_non_retryable_and_redacted(failure: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("test-api-key sentinel transport detail", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel server body", request=request)
        return httpx.Response(200, text="not-json", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.storage.upload(
            namespace_id=NAMESPACE_ID,
            path="ambiguous.bin",
            source=io.BytesIO(CONTENT),
        )

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert "test-api-key" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_upload_rejects_malformed_rest_receipt_as_unknown_outcome() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"unexpected": True}, request=request)
    )

    with _client(transport) as client, pytest.raises(MutationOutcomeUnknownError):
        client.storage.upload(
            namespace_id=NAMESPACE_ID,
            path="malformed-receipt.bin",
            source=io.BytesIO(CONTENT),
        )


def test_receipt_models_are_immutable_and_strict() -> None:
    receipt = UploadReceipt(
        namespace_id=NAMESPACE_ID,
        path="file.bin",
        bytes_sent=len(CONTENT),
        sha256=hashlib.sha256(CONTENT).hexdigest(),
    )

    assert receipt.server_verified is False
    with pytest.raises((TypeError, ValueError)):
        receipt.path = "other.bin"


def test_transport_failures_are_not_retried_for_download() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ReadError("sentinel response detail", request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(TransportError):
        client.storage.download(
            namespace_id=NAMESPACE_ID,
            path="failed.bin",
            destination=io.BytesIO(),
        )

    assert requests == 1
