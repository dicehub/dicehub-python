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
@pytest.mark.parametrize(
    "domain", ["apps", "configs", "groups", "resources", "runs", "templates", "members"]
)
def test_oversized_cursor_raises_redacted_protocol_error(domain: str, async_mode: bool) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
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

    def sync(client: Client) -> object:
        if domain == "apps":
            return client.apps.list(project_id="1")
        if domain == "configs":
            return client.configs.list(app_id="1")
        if domain == "groups":
            return client.groups.list()
        if domain == "resources":
            return client.resources.list(namespace_id="1")
        if domain == "runs":
            return client.runs.list(namespace_id="1")
        if domain == "templates":
            return client.templates.list()
        return client.projects.list_user_members(project_id="1")

    async def asynchronous(client: AsyncClient) -> object:
        if domain == "apps":
            return await client.apps.list(project_id="1")
        if domain == "configs":
            return await client.configs.list(app_id="1")
        if domain == "groups":
            return await client.groups.list()
        if domain == "resources":
            return await client.resources.list(namespace_id="1")
        if domain == "runs":
            return await client.runs.list(namespace_id="1")
        if domain == "templates":
            return await client.templates.list()
        return await client.projects.list_user_members(project_id="1")

    with pytest.raises(ProtocolError) as caught:
        perform(handler, async_mode, sync, asynchronous)
    assert len(seen) == 1
    assert "sensitive-response" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("size", [MAX_TEXT_BYTES, MAX_TEXT_BYTES + 1])
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


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("phase", ["lookup", "write", "invalid_credentials", "success"])
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
