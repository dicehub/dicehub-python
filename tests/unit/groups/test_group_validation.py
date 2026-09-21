from __future__ import annotations

import httpx
import pytest

from dicehub import Client, ConfigurationError, GroupOrderField, GroupVisibility, SortOrder


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=handler,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"user_id": "01"},
        {"parent_id": "group"},
        {"search_filter": "bad\nfilter"},
        {"search_filter": "x" * 257},
        {"offset": -1},
        {"offset": True},
        {"offset": 2**53},
        {"limit": 0},
        {"limit": True},
        {"limit": 51},
        {"cursor": "bad cursor"},
        {"cursor": "x" * 16_385},
        {"order_by": "name"},
        {"order": "ASC"},
    ],
)
def test_list_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.groups.list(**kwargs)  # type: ignore[arg-type]

    assert request_count == 0


@pytest.mark.parametrize("group_id", ["", "0", "01", "+1", "one", " 1", "1 ", "\u0661"])
def test_get_validates_group_id_before_transport(group_id: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.groups.get(group_id=group_id)

    assert request_count == 0


@pytest.mark.parametrize(
    "route",
    ["", "dicehub/research", "/dicehub/\nresearch", "/dicehub/\0research", "/" + "x" * 16_384],
)
def test_get_by_route_rejects_unsafe_or_oversized_values(route: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.groups.get_by_route(route=route)

    assert request_count == 0


def test_list_accepts_all_supported_sort_enums() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "groups": {
                        "listGroups": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "groups": [],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        for order_by in GroupOrderField:
            for order in SortOrder:
                client.groups.list(order_by=order_by, order=order)

    assert calls == len(GroupOrderField) * len(SortOrder)


def test_update_requires_at_least_one_change_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.groups.update(group_id="73")

    assert request_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"group_id": "01", "name": "Updated group"},
        {"group_id": "73", "name": ""},
        {"group_id": "73", "name": "   "},
        {"group_id": "73", "name": "bad\nname"},
        {"group_id": "73", "name": "x" * 129},
        {"group_id": "73", "slug": "ab"},
        {"group_id": "73", "slug": "a" * 129},
        {"group_id": "73", "slug": "bad slug"},
        {"group_id": "73", "slug": "gr\N{LATIN SMALL LETTER U WITH DIAERESIS}ppe"},
        {"group_id": "73", "description": "bad\0description"},
        {"group_id": "73", "visibility": "PUBLIC"},
    ],
)
def test_update_validates_inputs_before_transport(kwargs: dict[str, object]) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(ConfigurationError):
        client.groups.update(**kwargs)  # type: ignore[arg-type]

    assert request_count == 0


def test_update_accepts_each_visibility_enum() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "groups": {
                        "updateGroup": {
                            "status": {"succeeded": True, "error": None},
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        for visibility in GroupVisibility:
            client.groups.update(group_id="73", visibility=visibility)

    assert calls == len(GroupVisibility)
