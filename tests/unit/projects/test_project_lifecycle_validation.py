from __future__ import annotations

from typing import Any

import httpx
import pytest

from dicehub import Client, ConfigurationError


def _assert_rejected(method_name: str, kwargs: dict[str, Any]) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            session_cookie="session",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(ConfigurationError),
    ):
        getattr(client.projects, method_name)(**kwargs)

    assert request_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "", "slug": "case"},
        {"name": "ab", "slug": "case"},
        {"name": "   ", "slug": "case"},
        {"name": "bad\nname", "slug": "case"},
        {"name": "x" * 129, "slug": "case"},
        {"name": "Case", "slug": "ab"},
        {"name": "Case", "slug": "bad slug"},
        {"name": "Case", "slug": "rös"},
        {"name": "Case", "slug": "x" * 129},
        {"name": "Case", "slug": "case", "group_id": "01"},
        {"name": "Case", "slug": "case", "description": "bad\0description"},
        {"name": "Case", "slug": "case", "visibility": "PRIVATE"},
    ],
)
def test_create_rejects_invalid_inputs(kwargs: dict[str, Any]) -> None:
    _assert_rejected("create", kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"project_id": "91"},
        {"project_id": "01", "name": "Case"},
        {"project_id": "91", "name": "ab"},
        {"project_id": "91", "slug": "bad slug"},
        {"project_id": "91", "description": "bad\0description"},
        {"project_id": "91", "visibility": "PUBLIC"},
    ],
)
def test_update_rejects_noop_and_invalid_inputs(kwargs: dict[str, Any]) -> None:
    _assert_rejected("update", kwargs)


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("move", {"project_id": "01", "to_group_id": "42"}),
        ("move", {"project_id": "91", "to_group_id": "group"}),
        ("delete", {"project_id": "-1"}),
    ],
)
def test_targeted_mutations_reject_invalid_ids(
    method_name: str,
    kwargs: dict[str, str],
) -> None:
    _assert_rejected(method_name, kwargs)
