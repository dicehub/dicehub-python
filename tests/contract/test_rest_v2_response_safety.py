"""Untrusted REST responses must preserve the SDK's public error contracts."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client
from dicehub.errors import MutationOutcomeUnknownError, ProtocolError, TransportError
from dicehub.resources._validation import MAX_TEXT_BYTES

RESOURCE_ID = "a4d5fcbe-c20c-4a16-96d4-a5fb4da43347"


def perform(
    handler: Callable[[httpx.Request], httpx.Response],
    async_mode: bool,
    sync: Callable[[Client], Any],
    asynchronous: Callable[[AsyncClient], Awaitable[Any]],
) -> Any:
    async def run() -> Any:
        async with AsyncClient(
            base_url="https://dicehub.test",
            session_cookie="test-session",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(handler),
        ) as client:
            return await asynchronous(client)

    if async_mode:
        return asyncio.run(run())
    with Client(
        base_url="https://dicehub.test",
        session_cookie="test-session",
        api_protocol="rest_v2",
        transport=httpx.MockTransport(handler),
    ) as client:
        return sync(client)


@pytest.mark.parametrize("async_mode", [False, True])
def test_oversized_cursor_raises_redacted_protocol_error(async_mode: bool) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET" and request.url.path == "/api/v2/apps"
        return httpx.Response(
            200,
            json={
                "items": [],
                "limit": 20,
                "offset": 0,
                "count": 0,
                "has_more": False,
                "cursor": "sensitive-response-" * 1000,
            },
        )

    with pytest.raises(ProtocolError) as caught:
        perform(
            handler,
            async_mode,
            lambda client: client.apps.list(project_id="1"),
            lambda client: client.apps.list(project_id="1"),
        )
    assert len(seen) == 1
    assert "sensitive-response" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("size", "async_mode"),
    [(MAX_TEXT_BYTES, False), (MAX_TEXT_BYTES + 1, False), (MAX_TEXT_BYTES + 1, True)],
)
def test_resource_text_preserves_utf8_byte_limit(size: int, async_mode: bool) -> None:
    content = "é" * (size // 2) + "x" * (size % 2)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/v2/resources/{RESOURCE_ID}/text"
        return httpx.Response(200, json={"content": content})

    def read() -> str:
        return str(
            perform(
                handler,
                async_mode,
                lambda client: client.resources.get_text(resource_id=RESOURCE_ID),
                lambda client: client.resources.get_text(resource_id=RESOURCE_ID),
            )
        )

    if size == MAX_TEXT_BYTES:
        assert read() == content
    else:
        with pytest.raises(ProtocolError) as caught:
            read()
        assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("phase", "async_mode"),
    [
        ("lookup", False),
        ("lookup", True),
        ("write", False),
        ("write", True),
        ("invalid_credentials", False),
        ("invalid_credentials", True),
        ("success", False),
    ],
)
def test_result_credentials_distinguish_read_and_write_failures(
    phase: str, async_mode: bool
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            assert request.url.path == "/api/v2/resources/by-key"
            if phase == "lookup":
                raise httpx.ReadTimeout("sensitive-response", request=request)
            return httpx.Response(
                200,
                json={
                    "resource_id": RESOURCE_ID,
                    "namespace_id": "1",
                    "key": f"data/run/{RESOURCE_ID}/result",
                    "resource_type": "FOLDER",
                },
            )
        assert request.method == "POST"
        assert request.url.path == f"/api/v2/resources/{RESOURCE_ID}/credentials"
        if phase == "write":
            raise httpx.ReadTimeout("sensitive-response", request=request)
        return httpx.Response(
            200,
            json={
                "bucket": RESOURCE_ID if phase == "success" else "sensitive-response",
                "access_key_id": "x" * 20,
                "secret_access_key": "x" * 40,
            },
        )

    def read() -> Any:
        return perform(
            handler,
            async_mode,
            lambda client: client.runs.get_result_s3_credentials(app_id="1", run_id=RESOURCE_ID),
            lambda client: client.runs.get_result_s3_credentials(app_id="1", run_id=RESOURCE_ID),
        )

    if phase == "success":
        credentials = read()
        assert credentials.bucket == RESOURCE_ID
        assert credentials.access_key_id.get_secret_value() == "x" * 20
        assert credentials.secret_access_key.get_secret_value() == "x" * 40
        assert "x" * 20 not in credentials.model_dump_json()
        assert len(seen) == 2
        return

    error_type = TransportError if phase == "lookup" else MutationOutcomeUnknownError
    with pytest.raises(error_type) as caught:
        read()
    assert len(seen) == (1 if phase == "lookup" else 2)
    assert "sensitive-response" not in str(caught.value)
    assert caught.value.__context__ is None
