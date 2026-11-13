"""REST summary requests must avoid valid but oversized unused detail fields."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("domain", ["groups", "apps", "teams"])
def test_summary_reads_omit_oversized_description(domain: str, async_mode: bool) -> None:
    summary: dict[str, Any] = {
        "name": "Example",
        "route": "/owner/example",
        "display_route": "Owner/Example",
    }
    if domain == "groups":
        summary.update(group_id="42", parent_id=None, visibility="PUBLIC", has_children=False)
    elif domain == "apps":
        summary.update(app_id="42", project_id="7", visibility="PUBLIC", app_type="REGULAR")
    else:
        summary.update(team_id="42", group_id="7")
    detail = {**summary, "description": "x" * 100000}
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/api/v2/" + domain + ("/by-route" if domain == "teams" else "")
        assert request.url.params["view"] == "summary"
        body = summary if request.url.params.get("view") == "summary" else detail
        if domain != "teams":
            body = {
                "items": [body],
                "limit": 1,
                "offset": 0,
                "count": 1,
                "cursor": "",
                "has_more": False,
            }
        return httpx.Response(200, json=body)

    async def perform_async() -> Any:
        async with AsyncClient(
            base_url="http://localhost",
            api_key="test-token",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(handle),
        ) as client:
            if domain == "groups":
                return (await client.groups.list(limit=1)).groups[0]
            if domain == "apps":
                return (await client.apps.list(project_id="7", limit=1)).apps[0]
            return await client.teams.get_by_route(route="/owner/example")

    def perform_sync() -> Any:
        with Client(
            base_url="http://localhost",
            api_key="test-token",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(handle),
        ) as client:
            if domain == "groups":
                return client.groups.list(limit=1).groups[0]
            if domain == "apps":
                return client.apps.list(project_id="7", limit=1).apps[0]
            return client.teams.get_by_route(route="/owner/example")

    result = asyncio.run(perform_async()) if async_mode else perform_sync()
    assert result.name == "Example"
    assert not hasattr(result, "description")
    assert len(seen) == 1
