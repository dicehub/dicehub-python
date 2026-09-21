from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from dicehub import Client, NamespacePermission, ProtocolError
from dicehub.api_keys import service as service_module

PAGE_SIZE = 20


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=handler,
    )


def _api_key(api_key_id: int, *, large: bool = False) -> dict[str, object]:
    return {
        "apiKeyId": str(api_key_id),
        "name": "x" * 120 if large else f"key-{api_key_id}",
        "prefix": "12345",
        "permissions": [NamespacePermission.VIEW_PROJECT_INFO.value],
        "createdAt": "2026-08-11T09:10:11.123",
        "updatedAt": "2026-08-11T10:11:12.456Z",
        "lastUsedAt": None,
        "status": "ACTIVE",
        "notBefore": None,
        "expiresAt": None,
        "validityStatus": "ACTIVE",
    }


def _response(
    request: httpx.Request,
    page: list[dict[str, object]] | None,
) -> httpx.Response:
    body = {
        "data": {
            "apiKeys": {
                "listApiKeys": {
                    "status": {"succeeded": True, "error": None},
                    "apiKeys": page,
                }
            }
        }
    }
    assert len(json.dumps(body).encode("utf-8")) < 64 * 1024
    return httpx.Response(200, json=body, request=request)


def _assert_generic_protocol_error(action: Callable[[], object]) -> None:
    with pytest.raises(ProtocolError) as captured:
        action()
    assert str(captured.value) == "dicehub returned an invalid API-key listing."


def test_list_aggregates_pages_larger_than_single_response_limit() -> None:
    raw_keys = [_api_key(api_key_id, large=True) for api_key_id in range(10_000, 9_780, -1)]
    assert len(json.dumps(raw_keys).encode("utf-8")) > 64 * 1024
    index_by_id = {item["apiKeyId"]: index for index, item in enumerate(raw_keys)}
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListApiKeys"
        assert "beforeApiKeyId" in payload["query"]
        assert "value" not in payload["query"]
        variables = payload["variables"]
        requests.append(variables)
        before = variables["beforeApiKeyId"]
        start = 0 if before is None else index_by_id[before] + 1
        return _response(request, raw_keys[start : start + PAGE_SIZE])

    with _client(httpx.MockTransport(handler)) as client:
        listed = client.api_keys.list(namespace_id="42")

    assert [item.api_key_id for item in listed] == [item["apiKeyId"] for item in raw_keys]
    assert len(json.dumps([item.model_dump(mode="json") for item in listed])) > 64 * 1024
    assert len(requests) == 12
    assert requests[0] == {
        "namespaceId": "42",
        "beforeApiKeyId": None,
        "limit": PAGE_SIZE,
    }
    for index, variables in enumerate(requests[1:], start=1):
        assert variables == {
            "namespaceId": "42",
            "beforeApiKeyId": raw_keys[index * PAGE_SIZE - 1]["apiKeyId"],
            "limit": PAGE_SIZE,
        }


def test_list_rejects_page_larger_than_fixed_bound() -> None:
    page = [_api_key(api_key_id) for api_key_id in range(100, 79, -1)]
    transport = httpx.MockTransport(lambda request: _response(request, page))

    with _client(transport) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))


def test_list_rejects_id_outside_signed_bigint_before_cursor_request() -> None:
    page = [_api_key(2**63)]
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return _response(request, page)

    with _client(httpx.MockTransport(handler)) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))

    assert request_count == 1


@pytest.mark.parametrize(
    "ids",
    [
        [100, 99, 99],
        [100, 101],
    ],
)
def test_list_rejects_duplicate_or_non_descending_ids(ids: list[int]) -> None:
    page = [_api_key(api_key_id) for api_key_id in ids]
    transport = httpx.MockTransport(lambda request: _response(request, page))

    with _client(transport) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))


def test_list_rejects_cursor_non_progress() -> None:
    page = [_api_key(api_key_id) for api_key_id in range(100, 80, -1)]
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return _response(request, page)

    with _client(httpx.MockTransport(handler)) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))

    assert request_count == 2


def test_list_rejects_non_descending_id_across_pages() -> None:
    first_page = [_api_key(api_key_id) for api_key_id in range(100, 80, -1)]
    pages = [first_page, [_api_key(1_000)]]
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        page = pages[request_count]
        request_count += 1
        return _response(request, page)

    with _client(httpx.MockTransport(handler)) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))

    assert request_count == 2


def test_list_rejects_more_than_total_key_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "_MAX_LISTED_API_KEYS", 40)
    next_id = 1_000
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal next_id, request_count
        request_count += 1
        page = [_api_key(api_key_id) for api_key_id in range(next_id, next_id - 20, -1)]
        next_id -= 20
        return _response(request, page)

    with _client(httpx.MockTransport(handler)) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))

    assert request_count == 3


def test_list_rejects_more_than_request_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service_module, "_MAX_API_KEY_LIST_REQUESTS", 2)
    next_id = 1_000
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal next_id, request_count
        request_count += 1
        page = [_api_key(api_key_id) for api_key_id in range(next_id, next_id - 20, -1)]
        next_id -= 20
        return _response(request, page)

    with _client(httpx.MockTransport(handler)) as client:
        _assert_generic_protocol_error(lambda: client.api_keys.list(namespace_id="42"))

    assert request_count == 2


def test_list_production_safety_limits_are_pinned() -> None:
    assert service_module._API_KEY_LIST_PAGE_SIZE == 20
    assert service_module._MAX_API_KEY_NUMERIC_ID == 2**63 - 1
    assert service_module._MAX_LISTED_API_KEYS == 10_000
    assert service_module._MAX_API_KEY_LIST_REQUESTS == 501
