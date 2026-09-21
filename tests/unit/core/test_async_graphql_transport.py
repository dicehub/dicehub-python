from __future__ import annotations

import asyncio
import io
import threading
from collections.abc import AsyncIterator
from typing import BinaryIO, cast

import httpx
import pytest

from dicehub import (
    AuthenticationError,
    ConfigurationError,
    GraphQLError,
    HTTPError,
    ProtocolError,
    TransportError,
)
from dicehub._core.async_graphql import AsyncGraphQLTransport
from dicehub._core.graphql import GraphQLResult


def _transport(transport: httpx.AsyncBaseTransport) -> AsyncGraphQLTransport:
    return AsyncGraphQLTransport(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=transport,
    )


class _BlockingCloseTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {}}, request=request)

    async def aclose(self) -> None:
        self.close_started.set()
        await self.release_close.wait()


def test_execute_uses_async_client_and_fixed_origin() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": {"viewer": {"id": "42"}}}, request=request)

    async def scenario() -> GraphQLResult:
        transport = _transport(httpx.MockTransport(handler))
        try:
            return await transport.execute(
                operation_name="GetViewer",
                query="query GetViewer { viewer { id } }",
                variables={"includeEmail": False},
            )
        finally:
            await transport.aclose()

    result = asyncio.run(scenario())

    assert result.data == {"viewer": {"id": "42"}}
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url == "https://dicehub.test/api/graphql/"
    assert request.headers["authorization"] == "Bearer test-api-key"
    assert request.headers["accept-encoding"] == "identity"


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(401, AuthenticationError), (403, AuthenticationError), (503, HTTPError)],
)
def test_execute_maps_http_errors_without_retry(
    status_code: int,
    error_type: type[Exception],
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, request=request)

    async def scenario() -> None:
        transport = _transport(httpx.MockTransport(handler))
        try:
            with pytest.raises(error_type):
                await transport.execute(operation_name="Failure", query="query Failure { x }")
        finally:
            await transport.aclose()

    asyncio.run(scenario())
    assert calls == 1


def test_execute_preserves_response_limits_and_graphql_error_mapping() -> None:
    async def oversized_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (64 * 1024 + 1), request=request)

    async def graphql_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"message": "sensitive server detail"}]},
            request=request,
        )

    async def scenario() -> None:
        oversized = _transport(httpx.MockTransport(oversized_handler))
        try:
            with pytest.raises(ProtocolError, match="larger than 64 KiB"):
                await oversized.execute(operation_name="Large", query="query Large { x }")
        finally:
            await oversized.aclose()

        graphql = _transport(httpx.MockTransport(graphql_handler))
        try:
            with pytest.raises(GraphQLError) as captured:
                await graphql.execute(operation_name="Failure", query="query Failure { x }")
            assert "sensitive" not in str(captured.value)
        finally:
            await graphql.aclose()

    asyncio.run(scenario())


async def _chunks() -> AsyncIterator[bytes]:
    yield b"first-"
    await asyncio.sleep(0)
    yield b"second"


def test_upload_binary_consumes_async_iterable() -> None:
    received = bytearray()

    async def handler(request: httpx.Request) -> httpx.Response:
        received.extend(await request.aread())
        return httpx.Response(
            200,
            json={"status": {"succeeded": True, "error": None}},
            request=request,
        )

    async def scenario() -> dict[str, object]:
        transport = _transport(httpx.MockTransport(handler))
        try:
            return await transport.upload_binary(
                path="api/v1/storage/42/input.bin",
                chunks=_chunks(),
                method="POST",
            )
        finally:
            await transport.aclose()

    payload = asyncio.run(scenario())

    assert received == b"first-second"
    assert payload == {"status": {"succeeded": True, "error": None}}


class _ThreadTrackingDestination:
    def __init__(self) -> None:
        self.content = bytearray()
        self.thread_ids: list[int] = []

    def write(self, chunk: bytes) -> int:
        self.thread_ids.append(threading.get_ident())
        self.content.extend(chunk)
        return len(chunk)


def test_download_binary_writes_in_worker_threads_and_enforces_media_type() -> None:
    destination = _ThreadTrackingDestination()
    event_loop_thread = threading.get_ident()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"downloaded content",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    async def scenario() -> int:
        transport = _transport(httpx.MockTransport(handler))
        try:
            return await transport.download_binary(
                path="api/v1/storage/42/output.bin",
                destination=cast(BinaryIO, destination),
                max_bytes=1024,
                expected_media_type="application/octet-stream",
            )
        finally:
            await transport.aclose()

    count = asyncio.run(scenario())

    assert count == len(b"downloaded content")
    assert destination.content == b"downloaded content"
    assert destination.thread_ids
    assert all(thread_id != event_loop_thread for thread_id in destination.thread_ids)


def test_download_binary_preserves_transfer_errors_and_limits() -> None:
    destination = io.BytesIO()

    async def too_large(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"0123456789",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive timeout detail", request=request)

    async def scenario() -> None:
        large = _transport(httpx.MockTransport(too_large))
        try:
            with pytest.raises(ProtocolError, match="larger than the configured limit"):
                await large.download_binary(
                    path="api/v1/storage/42/output.bin",
                    destination=cast(BinaryIO, destination),
                    max_bytes=3,
                )
        finally:
            await large.aclose()

        failed = _transport(httpx.MockTransport(timeout))
        try:
            with pytest.raises(TransportError) as captured:
                await failed.download_binary(
                    path="api/v1/storage/42/output.bin",
                    destination=cast(BinaryIO, destination),
                    max_bytes=1024,
                )
            assert "sensitive" not in str(captured.value)
        finally:
            await failed.aclose()

    asyncio.run(scenario())


def test_aclose_is_idempotent_and_cancelled_error_is_not_wrapped() -> None:
    async def cancelled(request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError()

    async def scenario() -> None:
        transport = _transport(httpx.MockTransport(cancelled))
        await transport.aclose()
        await transport.aclose()

        with pytest.raises(ConfigurationError, match="client is closed"):
            await transport.execute(operation_name="Closed", query="query Closed { x }")

        active = _transport(httpx.MockTransport(cancelled))
        try:
            with pytest.raises(asyncio.CancelledError):
                await active.execute(operation_name="Cancelled", query="query Cancelled { x }")
        finally:
            await active.aclose()

    asyncio.run(scenario())


def test_execute_during_aclose_reports_closed_configuration() -> None:
    async def scenario() -> None:
        blocking = _BlockingCloseTransport()
        transport = _transport(blocking)
        close_task = asyncio.create_task(transport.aclose())
        try:
            await blocking.close_started.wait()
            with pytest.raises(ConfigurationError, match="client is closed"):
                await asyncio.gather(
                    transport.execute(
                        operation_name="ClosedDuringClose",
                        query="query ClosedDuringClose { x }",
                    ),
                    close_task,
                )
        finally:
            blocking.release_close.set()
            await close_task

    asyncio.run(scenario())
