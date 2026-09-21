from __future__ import annotations

import os

import pytest

from dicehub import Client, TemplateType

_DEFAULT_TEMPLATE_ROUTE = "/templates/openfoam_snappyhexmesh"


def _client(base_url: str) -> Client:
    api_key = os.environ.get("DICEHUB_API_KEY")
    if api_key is not None:
        return Client(base_url=base_url, api_key=api_key)

    session_cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if session_cookie is not None:
        return Client(base_url=base_url, session_cookie=session_cookie)

    pytest.skip("DICEHUB_API_KEY or DICEHUB_SESSION_COOKIE is not set.")


@pytest.mark.integration
@pytest.mark.live
def test_live_template_discovery() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live requests.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    route = os.environ.get("DICEHUB_LIVE_TEMPLATE_ROUTE", _DEFAULT_TEMPLATE_ROUTE)

    with _client(base_url) as client:
        by_route = client.templates.get_by_route(route=route)
        by_id = client.templates.get(template_id=by_route.template_id)
        page = client.templates.list(
            search_filter=by_route.name,
            template_type=TemplateType.APP_TEMPLATE,
            limit=50,
        )
        matches = [
            template for template in page.templates if template.template_id == by_route.template_id
        ]

    assert len(matches) == 1
    assert matches[0] == by_route == by_id
