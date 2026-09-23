from __future__ import annotations

import httpx
import pytest

from dicehub import AppOrderField, Client, ConfigurationError, SortOrder


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid app input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


def test_list_rejects_invalid_project_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.list(project_id="01")


def test_get_rejects_invalid_app_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.get(app_id="01")


@pytest.mark.parametrize("field", ["project_id", "template_id"])
def test_create_rejects_invalid_ids(field: str) -> None:
    arguments = {
        "project_id": "41",
        "template_id": "9",
        "name": "Agent app",
        field: "01",
    }
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.create(**arguments)


def test_create_rejects_invalid_name() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.create(project_id="41", template_id="9", name="ab")


def test_create_rejects_nul_description() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.create(
            project_id="41",
            template_id="9",
            name="Agent app",
            description="bad\0description",
        )


def test_update_requires_at_least_one_change() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.update(app_id="101")


def test_update_rejects_invalid_app_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.update(app_id="01", description="Updated")


def test_delete_rejects_invalid_app_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.delete(app_id="01")


def test_update_rejects_invalid_fields() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.update(app_id="101", name="ab")
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.update(app_id="101", description="bad\0description")


def test_get_by_route_rejects_invalid_route() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.get_by_route(route="relative")


@pytest.mark.parametrize(
    "values",
    [
        {"search_filter": "bad\nfilter"},
        {"offset": 2**53},
        {"limit": 51},
        {"cursor": "bad cursor"},
    ],
)
def test_list_rejects_invalid_filters_and_pagination(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.list(project_id="41", **values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "values",
    [
        {"order_by": "name"},
        {"order": "ASC"},
        {"is_published": 1},
    ],
)
def test_list_rejects_untyped_enum_and_boolean_values(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.apps.list(project_id="41", **values)  # type: ignore[arg-type]


def test_list_accepts_all_supported_sort_fields() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "apps": {
                        "listApps": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "apps": [],
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
        for field in AppOrderField:
            client.apps.list(project_id="41", order_by=field, order=SortOrder.ASC)

    assert calls == len(AppOrderField)
