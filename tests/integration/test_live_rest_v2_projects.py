from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from dicehub import AsyncClient, Client, ProjectOrderField, SortOrder


def compare_projects(
    *,
    base_url: str,
    project_id: str,
    api_key: str | None = None,
    session_cookie: str | None = None,
    user_id: str | None = None,
) -> int:
    """Read-only parity check, also used with disposable deployment fixtures."""
    checks = 0
    with (
        Client(base_url=base_url, api_key=api_key, session_cookie=session_cookie) as graphql,
        Client(
            base_url=base_url,
            api_key=api_key,
            session_cookie=session_cookie,
            project_reads="rest_v2",
        ) as rest,
    ):
        expected = graphql.projects.get(project_id=project_id)
        assert rest.projects.get(project_id=project_id) == expected
        assert rest.projects.get_by_route(route=expected.route) == graphql.projects.get_by_route(
            route=expected.route
        )
        checks += 2
        queries: list[dict[str, Any]] = [
            {},
            {"group_id": expected.group_id},
            {"search_filter": expected.name},
            {"search_filter": "sdk-no-match-94188"},
        ]
        if user_id is not None:
            queries.extend(
                [{"user_id": user_id}, {"user_id": user_id, "group_id": expected.group_id}]
            )
        for order_by in ProjectOrderField:
            for order in SortOrder:
                for query in queries:
                    options = dict(query, order_by=order_by, order=order, limit=1)
                    gql_page = graphql.projects.list(**options)
                    rest_page = rest.projects.list(**options)
                    assert rest_page == gql_page
                    checks += 1
                    # Bound live reads; do not traverse an arbitrary installation.
                    for offset in (1, 2):
                        if offset >= gql_page.count:
                            break
                        gql_page = graphql.projects.list(
                            **options, offset=offset, cursor=gql_page.cursor
                        )
                        rest_page = rest.projects.list(
                            **options, offset=offset, cursor=rest_page.cursor
                        )
                        assert rest_page == gql_page
                        checks += 1

        async def asynchronous() -> None:
            async with AsyncClient(
                base_url=base_url,
                api_key=api_key,
                session_cookie=session_cookie,
                project_reads="rest_v2",
            ) as sdk:
                assert await sdk.projects.get(project_id=project_id) == expected
                assert await sdk.projects.get_by_route(route=expected.route) == expected
                assert await sdk.projects.list(
                    group_id=expected.group_id, limit=1
                ) == graphql.projects.list(group_id=expected.group_id, limit=1)

        asyncio.run(asynchronous())
    return checks + 3


@pytest.mark.live
@pytest.mark.integration
def test_live_rest_v2_projects_match_graphql() -> None:
    if (
        os.environ.get("DICEHUB_LIVE_TEST") != "1"
        or os.environ.get("DICEHUB_LIVE_REST_V2_TEST") != "1"
    ):
        pytest.skip("Set DICEHUB_LIVE_TEST=1 and DICEHUB_LIVE_REST_V2_TEST=1.")
    project_id = os.environ.get("DICEHUB_LIVE_PROJECT_ID")
    if not project_id:
        pytest.skip("Set DICEHUB_LIVE_PROJECT_ID to one visible project.")
    compare_projects(
        base_url=os.environ.get("DICEHUB_URL", "http://127.0.0.1:18090"),
        project_id=project_id,
        api_key=os.environ.get("DICEHUB_API_KEY"),
        session_cookie=os.environ.get("DICEHUB_SESSION_COOKIE"),
        user_id=os.environ.get("DICEHUB_LIVE_USER_ID"),
    )
