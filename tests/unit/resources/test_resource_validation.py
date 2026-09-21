from __future__ import annotations

import httpx
import pytest

from dicehub import Client, ConfigurationError, ResourceType, SortOrder

RESOURCE_ID = "12345678-1234-5678-9234-567812345678"


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid resource input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


@pytest.mark.parametrize("namespace_id", ["", "0", "01", "abc", "1" * 257])
def test_namespace_id_must_be_a_positive_decimal_id(namespace_id: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.list(namespace_id=namespace_id)


@pytest.mark.parametrize(
    "resource_id", ["", "0", "not-a-uuid", "12345678-1234-5678-9234-56781234567"]
)
def test_resource_id_must_be_a_canonical_uuid(resource_id: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.get(resource_id=resource_id)


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "trailing/",
        "../escape",
        "nested/../escape",
        "a/./b",
        "a//b",
        "back\\slash",
        "bad\npath",
        "x" * 16_385,
    ],
)
def test_resource_paths_reject_traversal_controls_and_overlong_input(path: str) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.get_by_key(namespace_id="101", path=path)


def test_resource_list_allows_the_data_root_default_path() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "resources": {
                        "listResources": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "resources": [],
                        }
                    }
                }
            },
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.resources.list(namespace_id="101")

    assert calls == 1


@pytest.mark.parametrize(
    "values",
    [
        {"resource_type": "FILE"},
        {"recursive": 1},
        {"order": "ASC"},
        {"offset": -1},
        {"offset": True},
        {"offset": 2**53},
        {"limit": 0},
        {"limit": True},
        {"limit": 51},
        {"cursor": "bad\ncursor"},
        {"cursor": "x" * 16_385},
    ],
)
def test_resource_list_rejects_untyped_filters_and_invalid_pagination(
    values: dict[str, object],
) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.list(namespace_id="101", **values)  # type: ignore[arg-type]


def test_resource_list_accepts_all_supported_resource_types_and_sort_orders() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "resources": {
                        "listResources": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "resources": [],
                        }
                    }
                }
            },
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        for resource_type in ResourceType:
            for order in SortOrder:
                client.resources.list(
                    namespace_id="101",
                    resource_type=resource_type,
                    order=order,
                )

    assert calls == len(ResourceType) * len(SortOrder)


def test_text_write_rejects_oversized_or_invalid_utf8_content() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.create_text(
            namespace_id="101",
            path="input.txt",
            content="x" * (2 * 1024 * 1024 + 1),
        )

    with _client() as client, pytest.raises(ConfigurationError, match="valid UTF-8"):
        client.resources.set_text(resource_id=RESOURCE_ID, content="\ud800")


def test_get_by_key_requires_a_nonempty_relative_path() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.resources.get_by_key(namespace_id="101", path="")
