"""Managed-key REST requests preserve pagination, permissions, and secret handling."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client
from dicehub.api_keys import NamespacePermission
from dicehub.errors import ConfigurationError, ProtocolError
from tests.contract.test_rest_v2_response_safety import perform


def metadata(key_id: str) -> dict[str, object]:
    return {
        "api_key_id": key_id,
        "name": "Automation",
        "prefix": "prefix",
        "permissions": ["VIEW_RESOURCE_INFO", "READ_RESOURCE_CONTENT"],
        "created_at": "2026-11-13T10:00:00Z",
        "updated_at": "2026-11-13T10:00:00Z",
        "last_used_at": None,
        "status": "ACTIVE",
        "not_before": None,
        "expires_at": None,
        "validity_status": "ACTIVE",
    }


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("overlap", [False, True])
def test_key_pages_use_exclusive_cursor_and_reject_duplicates(
    async_mode: bool, overlap: bool
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/v2/namespaces/1/api-keys"
        assert "authorization" not in request.headers
        assert request.headers["cookie"] == "_dicehub_session=test-session"
        assert request.url.params["limit"] == "20"
        if len(seen) == 1:
            assert "before_api_key_id" not in request.url.params
            items = [metadata(str(number)) for number in range(30, 10, -1)]
        else:
            assert request.url.params["before_api_key_id"] == "11"
            items = [metadata("11" if overlap else "10")]
        return httpx.Response(200, json={"items": items})

    def read() -> Any:
        return perform(
            handler,
            async_mode,
            lambda client: client.api_keys.list(namespace_id="1"),
            lambda client: client.api_keys.list(namespace_id="1"),
        )

    if overlap:
        with pytest.raises(ProtocolError) as caught:
            read()
        assert caught.value.__context__ is None
    else:
        keys = read()
        assert len(keys) == 21 and keys[-1].api_key_id == "10"
        assert keys[0].permissions == (
            NamespacePermission.VIEW_RESOURCE_INFO,
            NamespacePermission.READ_RESOURCE_CONTENT,
        )
        assert not hasattr(keys[0], "value")
    assert len(seen) == 2


@pytest.mark.parametrize("async_mode", [False, True])
def test_created_key_secret_survives_mapping_without_public_serialization(async_mode: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v2/namespaces/1/api-keys"
        assert request.headers["x-dicehub-request"] == "rest-v2"
        assert json.loads(request.content) == {
            "name": "Automation",
            "permissions": ["VIEW_RESOURCE_INFO", "READ_RESOURCE_CONTENT"],
        }
        return httpx.Response(201, json={**metadata("10"), "value": "creation-only-test-value"})

    permissions = [
        NamespacePermission.VIEW_RESOURCE_INFO,
        NamespacePermission.READ_RESOURCE_CONTENT,
    ]
    key = perform(
        handler,
        async_mode,
        lambda client: client.api_keys.create(
            namespace_id="1", name="Automation", permissions=permissions
        ),
        lambda client: client.api_keys.create(
            namespace_id="1", name="Automation", permissions=permissions
        ),
    )
    assert key.value.get_secret_value() == "creation-only-test-value"
    assert "creation-only-test-value" not in key.model_dump_json()
    assert "creation-only-test-value" not in repr(key)


@pytest.mark.parametrize("async_mode", [False, True])
def test_missing_key_returns_none(async_mode: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/namespaces/1/api-keys/10"
        return httpx.Response(404, text="sensitive-response")

    assert (
        perform(
            handler,
            async_mode,
            lambda client: client.api_keys.get(namespace_id="1", api_key_id="10"),
            lambda client: client.api_keys.get(namespace_id="1", api_key_id="10"),
        )
        is None
    )


@pytest.mark.parametrize("async_mode", [False, True])
def test_key_administration_keeps_session_only_guard(async_mode: bool) -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("Session-only operation must fail before HTTP.")

    async def run() -> None:
        async with AsyncClient(
            api_key="test-key",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(forbidden),
        ) as client:
            await client.api_keys.list(namespace_id="1")

    with pytest.raises(ConfigurationError, match="session-cookie"):
        if async_mode:
            asyncio.run(run())
        else:
            with Client(
                api_key="test-key",
                api_protocol="rest_v2",
                transport=httpx.MockTransport(forbidden),
            ) as client:
                client.api_keys.list(namespace_id="1")
