from __future__ import annotations

import asyncio

import httpx
import pytest

from dicehub import APIError, AsyncClient, ConfigurationError, ProtocolError, TransportError
from tests.contract.test_rest_v2_projects import page, project


def test_async_rest_reads_pagination_and_lifecycle() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200, json=page() if request.url.path == "/api/v2/projects" else project()
        )

    async def run() -> None:
        sdk = AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-key",
            project_reads="rest_v2",
            transport=httpx.MockTransport(handler),
        )
        async with sdk:
            result = await sdk.projects.list(limit=1)
            detail = await sdk.projects.get(project_id=result.projects[0].project_id)
            assert await sdk.projects.get_by_route(route=detail.route) == detail
        with pytest.raises(ConfigurationError, match="closed"):
            await sdk.projects.get(project_id="42")

    asyncio.run(run())
    assert len(requests) == 3 and all(r.method == "GET" for r in requests)


@pytest.mark.parametrize("failure", ["permission", "size", "timeout", "malformed", "encoding"])
def test_async_failures_are_bounded_sanitized_and_not_retried(failure: str) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("sentinel-secret", request=request)
        if failure == "permission":
            return httpx.Response(403, text="sentinel-secret")
        if failure == "size":
            return httpx.Response(
                200, content=b"x" * 65537, headers={"content-type": "application/json"}
            )
        if failure == "encoding":
            return httpx.Response(200, json=project(), headers={"content-encoding": "br"})
        return httpx.Response(200, json={"secret": "sentinel-secret"})

    async def run() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            session_cookie="test-session",
            project_reads="rest_v2",
            transport=httpx.MockTransport(handler),
        ) as sdk:
            with pytest.raises((APIError, ProtocolError, TransportError)) as caught:
                await sdk.projects.get(project_id="42")
            assert "sentinel-secret" not in str(caught.value)
            assert caught.value.__context__ is None

    asyncio.run(run())
    assert len(requests) == 1
    assert requests[0].headers["cookie"] == "_dicehub_session=test-session"


def test_async_request_cancellation_is_not_converted_or_retried() -> None:
    async def run() -> None:
        started = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            started.set()
            await asyncio.Event().wait()
            return httpx.Response(200, json=project())

        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-key",
            project_reads="rest_v2",
            transport=httpx.MockTransport(handler),
        ) as sdk:
            task = asyncio.create_task(sdk.projects.get(project_id="42"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())


def test_async_oversized_encoded_route_raises_safe_configuration_error() -> None:
    async def unexpected(_: httpx.Request) -> httpx.Response:
        pytest.fail("unexpected HTTP request")

    async def run() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-key",
            project_reads="rest_v2",
            transport=httpx.MockTransport(unexpected),
        ) as sdk:
            with pytest.raises(ConfigurationError) as caught:
                await sdk.projects.get_by_route(route="/" + "日本" * 8191)
            assert caught.value.__context__ is None
            assert "日本" not in str(caught.value)

    asyncio.run(run())


def test_async_pathological_json_is_a_sanitized_protocol_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"number":' + b"9" * 5000 + b"}",
            headers={"content-type": "application/json"},
        )

    async def run() -> None:
        async with AsyncClient(
            base_url="https://dicehub.test",
            api_key="test-key",
            project_reads="rest_v2",
            transport=httpx.MockTransport(handler),
        ) as sdk:
            with pytest.raises(ProtocolError) as caught:
                await sdk.projects.get(project_id="42")
            assert caught.value.__context__ is None

    asyncio.run(run())
