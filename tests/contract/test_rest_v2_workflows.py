"""The REST option must keep typed results, grants, and mutation failure semantics."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client
from dicehub.configs.models import ConfigContentArea
from dicehub.errors import ConfigurationError, MutationOutcomeUnknownError, ProtocolError

RUN_ID = "a4d5fcbe-c20c-4a16-96d4-a5fb4da43347"
CONFIG: dict[str, Any] = {
    "config_id": "12",
    "app_id": "10",
    "config_internal_id": "2",
    "name": "Config",
    "description": None,
    "is_default": False,
    "template_version": "1",
    "updating": False,
}
STATUS: dict[str, Any] = {
    "run_id": RUN_ID,
    "state": "RUNNING",
    "execution_status": None,
    "error": "NONE",
    "flags": ["STARTING"],
    "updated_at": "2026-10-04T10:00:00Z",
}


def test_config_content_and_run_workflow_uses_rest_only() -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "localhost"
        assert request.headers["authorization"] == "Bearer test-token"
        seen.append((request.method, request.url.path))
        if request.method != "GET":
            assert request.headers["x-dicehub-request"] == "rest-v2"
        if request.url.path == "/api/v2/configs" and request.method == "POST":
            assert json.loads(request.content) == {"app_id": "10", "name": "Config"}
            return httpx.Response(201, json=CONFIG)
        if request.url.path.endswith("/content"):
            assert request.url.params["area"] == "TEXTS"
            return httpx.Response(
                200,
                json={
                    "items": [{"path": "input.yaml", "resource_type": "TEXT"}],
                    "limit": 1,
                    "offset": 0,
                    "count": 2,
                    "cursor": "opaque",
                    "has_more": True,
                },
            )
        if request.url.path.endswith("/runs"):
            assert json.loads(request.content) == {
                "machine_type_id": "local",
                "node_count": 1,
                "notify": False,
            }
            return httpx.Response(201, json=STATUS)
        if request.url.path.endswith("/status"):
            assert not request.url.params
            return httpx.Response(200, json=STATUS)
        if request.method == "DELETE":
            assert request.content == b""
        return httpx.Response(200, json={"succeeded": True})

    with Client(
        base_url="http://localhost",
        api_key="test-token",
        api_protocol="rest_v2",
        transport=httpx.MockTransport(handle),
    ) as client:
        config = client.configs.create(app_id="10", name="Config")
        page = client.configs.list_content(
            config_id=config.config_id, area=ConfigContentArea.TEXTS, limit=1
        )
        assert page.count == 2 and page.cursor == "opaque"
        client.configs.set_text(config_id="12", path="input.yaml", content="a: 1")
        started = client.runs.start(config_id="12", machine_type_id="local")
        assert client.runs.status(run_id=started.run_id) == started
        client.runs.stop(run_id=started.run_id)
        client.configs.delete(config_id="12")
    assert seen == [
        ("POST", "/api/v2/configs"),
        ("GET", "/api/v2/configs/12/content"),
        ("PUT", "/api/v2/configs/12/text"),
        ("POST", "/api/v2/configs/12/runs"),
        ("GET", f"/api/v2/runs/{RUN_ID}/status"),
        ("POST", f"/api/v2/runs/{RUN_ID}/stop"),
        ("DELETE", "/api/v2/configs/12"),
    ]


@pytest.mark.parametrize("failure", ["timeout", "status", "extra"])
@pytest.mark.parametrize("async_mode", [False, True])
def test_mutation_failure_is_unknown_once_and_redacted(failure: str, async_mode: bool) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/v2/configs"
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive server body", request=request)
        if failure == "status":
            return httpx.Response(503, text="sensitive server body")
        return httpx.Response(201, json={**CONFIG, "private": "sensitive server body"})

    async def perform() -> None:
        async with AsyncClient(
            base_url="http://localhost",
            api_key="test-token",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(handle),
        ) as client:
            await client.configs.create(app_id="10", name="Config")

    with pytest.raises(MutationOutcomeUnknownError) as caught:
        if async_mode:
            asyncio.run(perform())
        else:
            with Client(
                base_url="http://localhost",
                api_key="test-token",
                api_protocol="rest_v2",
                transport=httpx.MockTransport(handle),
            ) as client:
                client.configs.create(app_id="10", name="Config")
    assert len(requests) == 1
    assert "sensitive" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "change",
    [
        {"offset": 3, "count": 4},
        {"count": 0},
        {"has_more": True},
    ],
)
def test_inconsistent_cursor_page_is_rejected(change: dict[str, object]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cursor"] == "previous"
        return httpx.Response(
            200,
            json={
                "items": [CONFIG],
                "limit": 1,
                "offset": 0,
                "count": 1,
                "has_more": False,
                "cursor": "next",
                **change,
            },
        )

    with Client(
        base_url="http://localhost",
        api_key="test-token",
        api_protocol="rest_v2",
        transport=httpx.MockTransport(handle),
    ) as client:
        with pytest.raises(ProtocolError):
            client.configs.list(app_id="10", limit=1, cursor="previous")


def test_rest_ids_are_bounded_before_any_http() -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No HTTP request is permitted")

    with Client(
        base_url="http://localhost",
        api_key="test-token",
        api_protocol="rest_v2",
        transport=httpx.MockTransport(forbidden),
    ) as client:
        with pytest.raises(ConfigurationError):
            client.apps.get(app_id=str(2**63))
        with pytest.raises(ConfigurationError):
            client.configs.create(app_id=str(2**63), name="Config")
        with pytest.raises(ConfigurationError):
            client.configs.list(app_id="10", offset=2**31)


def test_config_copy_maps_source_identifier() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "POST" and request.url.path == "/api/v2/configs"
        assert json.loads(request.content) == {
            "app_id": "10",
            "config_id": "11",
            "name": "Copy",
        }
        return httpx.Response(201, json=CONFIG)

    with Client(
        base_url="http://localhost",
        api_key="test-token",
        api_protocol="rest_v2",
        transport=httpx.MockTransport(handle),
    ) as client:
        result = client.configs.create(
            app_id="10",
            source_config_id="11",
            name="Copy",
        )
        assert result.config_id == CONFIG["config_id"]
    assert len(seen) == 1
