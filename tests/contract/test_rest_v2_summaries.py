"""REST reads select the summary view when detail fields are not needed."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from dicehub import AsyncClient, Client


@pytest.mark.parametrize(("domain", "async_mode"), [("groups", False), ("teams", True)])
def test_summary_reads_select_summary_view(domain: str, async_mode: bool) -> None:
    summary: dict[str, Any] = {
        "name": "Example",
        "route": "/owner/example",
        "display_route": "Owner/Example",
    }
    if domain == "groups":
        summary.update(group_id="42", parent_id=None, visibility="PUBLIC", has_children=False)
    else:
        summary.update(team_id="42", group_id="7")
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.path == "/api/v2/" + domain + ("/by-route" if domain == "teams" else "")
        assert request.url.params["view"] == "summary"
        body = summary
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
            return await client.teams.get_by_route(route="/owner/example")

    def perform_sync() -> Any:
        with Client(
            base_url="http://localhost",
            api_key="test-token",
            api_protocol="rest_v2",
            transport=httpx.MockTransport(handle),
        ) as client:
            return client.groups.list(limit=1).groups[0]

    result = asyncio.run(perform_async()) if async_mode else perform_sync()
    assert result.name == "Example"
    assert not hasattr(result, "description")
    assert len(seen) == 1
