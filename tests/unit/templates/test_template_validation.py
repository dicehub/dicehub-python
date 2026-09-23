from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from pydantic import ValidationError

from dicehub import (
    Client,
    ConfigurationError,
    SortOrder,
    Template,
    TemplateOrderField,
    TemplateTag,
    TemplateType,
)


def _client() -> Client:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Invalid template input must fail before HTTP.")

    return Client(
        base_url="https://dicehub.test",
        api_key="test-api-key",
        transport=httpx.MockTransport(forbidden),
    )


def _template(*, created_at: datetime | None, updated_at: datetime | None) -> Template:
    return Template(
        template_id="91",
        name="OpenFOAM",
        slug="openfoam",
        description=None,
        client_type="openfoam",
        route="/templates/openfoam",
        image_path=None,
        icon_path=None,
        tags=(TemplateTag(tag_id="12", tag="CFD"),),
        created_at=created_at,
        updated_at=updated_at,
    )


def test_public_template_timestamps_are_normalized_to_utc() -> None:
    source_timezone = timezone(timedelta(hours=2))
    template = _template(
        created_at=datetime(2026, 8, 13, 12, tzinfo=source_timezone),
        updated_at=datetime(2026, 8, 13, 13, tzinfo=source_timezone),
    )

    assert template.created_at == datetime(2026, 8, 13, 10, tzinfo=timezone.utc)
    assert template.updated_at == datetime(2026, 8, 13, 11, tzinfo=timezone.utc)
    assert template.created_at.tzinfo is timezone.utc
    assert template.updated_at.tzinfo is timezone.utc


def test_public_template_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _template(
            created_at=datetime(2026, 8, 13, 12),
            updated_at=datetime(2026, 8, 13, 13, tzinfo=timezone.utc),
        )


def test_get_rejects_invalid_template_id() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.templates.get(template_id="01")


def test_get_by_route_rejects_invalid_route() -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.templates.get_by_route(route="relative")


@pytest.mark.parametrize(
    "values",
    [
        {"search_filter": "bad\nfilter"},
        {"offset": 2**53},
        {"limit": 51},
        {"cursor": "bad cursor"},
        {"tags": []},
        {"tags": "CFD"},
        {"tags": ["CFD", "CFD"]},
        {"tags": [""]},
        {"tags": ["bad\ntag"]},
        {"tags": ["x" * 257]},
        {"tags": [str(index) for index in range(51)]},
    ],
)
def test_list_rejects_invalid_filters_and_pagination(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.templates.list(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "values",
    [
        {"template_type": "APP_TEMPLATE"},
        {"order_by": "name"},
        {"order": "ASC"},
    ],
)
def test_list_rejects_untyped_enum_values(values: dict[str, object]) -> None:
    with _client() as client, pytest.raises(ConfigurationError):
        client.templates.list(**values)  # type: ignore[arg-type]


def test_list_accepts_all_supported_enums() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "templates": {
                        "listTemplates": {
                            "status": {"succeeded": True, "error": None},
                            "info": {"offset": 0.0, "count": 0.0, "cursor": ""},
                            "templates": [],
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
        for template_type in TemplateType:
            for order_by in TemplateOrderField:
                for order in SortOrder:
                    client.templates.list(
                        template_type=template_type,
                        order_by=order_by,
                        order=order,
                    )

    assert calls == len(TemplateType) * len(TemplateOrderField) * len(SortOrder)
