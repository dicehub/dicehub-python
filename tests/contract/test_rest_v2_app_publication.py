"""App publication filters retain their meaning in both REST clients."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client
from dicehub.apps import AppPage
from dicehub.errors import APIError


@pytest.mark.parametrize(
    ("async_mode", "kwargs", "expected"),
    [
        (False, {}, "all"),
        (False, {"is_published": True}, "true"),
        (False, {"is_published": False}, "false"),
        (True, {"is_published": None}, "all"),
    ],
    ids=["sync-default", "sync-published", "sync-unpublished", "async-none"],
)
def test_publication_filter_on_each_page(
    async_mode: bool, kwargs: dict[str, Any], expected: str
) -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        offset = len(seen)
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/v2/apps"
        assert request.url.params["project_id"] == "7"
        assert request.url.params["view"] == "summary"
        assert request.url.params["is_published"] == expected
        assert request.url.params["offset"] == str(offset)
        assert request.url.params["limit"] == "1"
        assert request.url.params.get("cursor") == (None if offset == 0 else "page+1/=")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "app_id": str(offset + 1),
                        "project_id": "7",
                        "name": "Example",
                        "route": None,
                        "display_route": "Owner/Example",
                        "visibility": "PRIVATE",
                        "app_type": "REGULAR",
                    }
                ],
                "limit": 1,
                "offset": offset,
                "count": 2,
                "cursor": "page+1/=",
                "has_more": offset == 0,
            },
        )

    settings: dict[str, Any] = {
        "base_url": "http://localhost",
        "api_key": "test-token",
        "api_protocol": "rest_v2",
        "transport": httpx.MockTransport(handle),
    }

    async def perform_async() -> tuple[AppPage, AppPage]:
        async with AsyncClient(**settings) as client:
            first = await client.apps.list(project_id="7", limit=1, **kwargs)
            second = await client.apps.list(
                project_id="7", limit=1, offset=1, cursor=first.cursor, **kwargs
            )
            return first, second

    def perform_sync() -> tuple[AppPage, AppPage]:
        with Client(**settings) as client:
            first = client.apps.list(project_id="7", limit=1, **kwargs)
            second = client.apps.list(
                project_id="7", limit=1, offset=1, cursor=first.cursor, **kwargs
            )
            return first, second

    pages = asyncio.run(perform_async()) if async_mode else perform_sync()
    assert [app.app_id for page in pages for app in page.apps] == ["1", "2"]
    assert len(seen) == 2


def test_old_server_rejection_does_not_fall_back() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/api/v2/apps"
        assert request.url.params["is_published"] == "all"
        return httpx.Response(
            422,
            json={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "server-private-body",
                }
            },
        )

    settings: dict[str, Any] = {
        "base_url": "http://localhost",
        "api_key": "test-token",
        "api_protocol": "rest_v2",
        "transport": httpx.MockTransport(handle),
    }

    with pytest.raises(APIError) as caught:
        with Client(**settings) as client:
            client.apps.list(project_id="7")
    assert caught.value.server_code == "VALIDATION_FAILED"
    assert "server-private-body" not in str(caught.value)
    assert len(seen) == 1
