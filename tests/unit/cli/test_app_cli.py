from __future__ import annotations

import json
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import App, AppDetail, AppPage
from dicehub import cli as cli_module
from dicehub.apps import AppOrderField, AppType, AppVisibility
from dicehub.cli.commands import app as app_commands
from dicehub.projects import SortOrder

runner = CliRunner()


def _app(*, name: str = "Wind tunnel") -> App:
    return App(
        app_id="101",
        project_id="41",
        name=name,
        display_route="engineering / airfoil / Wind tunnel",
        route="/engineering/airfoil/101",
        visibility=AppVisibility.PRIVATE,
        app_type=AppType.REGULAR,
    )


def _app_detail(*, name: str = "Wind tunnel") -> AppDetail:
    return AppDetail(
        **_app(name=name).model_dump(),
        description="Transient CFD study",
        template_id="9",
        template_name="OpenFOAM",
        template_version="v13",
        template_slug="openfoam",
        icon_path="/assets/openfoam.svg",
        preview_url=None,
    )


class _FakeApps:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    detail: ClassVar[AppDetail] = _app_detail()

    def create(
        self,
        *,
        project_id: str,
        template_id: str,
        name: str,
        description: str | None = None,
    ) -> AppDetail:
        self.calls.append(
            (
                "create",
                {
                    "project_id": project_id,
                    "template_id": template_id,
                    "name": name,
                    "description": description,
                },
            )
        )
        return self.detail

    def update(
        self,
        *,
        app_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self.calls.append(
            (
                "update",
                {
                    "app_id": app_id,
                    "name": name,
                    "description": description,
                },
            )
        )

    def delete(self, *, app_id: str) -> None:
        self.calls.append(("delete", {"app_id": app_id}))

    def list(
        self,
        *,
        project_id: str,
        search_filter: str | None = None,
        order_by: AppOrderField = AppOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
        is_published: bool | None = None,
    ) -> AppPage:
        self.calls.append(
            (
                "list",
                {
                    "project_id": project_id,
                    "search_filter": search_filter,
                    "order_by": order_by,
                    "order": order,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                    "is_published": is_published,
                },
            )
        )
        return AppPage(apps=(_app(),), offset=offset, count=1, cursor="next")

    def get(self, *, app_id: str) -> AppDetail:
        self.calls.append(("get", {"app_id": app_id}))
        return self.detail

    def get_by_route(self, *, route: str) -> AppDetail:
        self.calls.append(("get_by_route", {"route": route}))
        return self.detail


class _FakeClient:
    apps = _FakeApps()
    constructions: ClassVar[list[dict[str, object]]] = []

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        self.constructions.append(
            {
                "base_url": base_url,
                "api_key": api_key,
                "session_cookie": session_cookie,
            }
        )

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeApps.calls = []
    _FakeApps.detail = _app_detail()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(app_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_list_uses_api_key_and_emits_structured_page() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "app",
            "list",
            "41",
            "--search",
            "wind",
            "--order-by",
            "UPDATED_AT",
            "--order",
            "desc",
            "--offset",
            "2",
            "--limit",
            "5",
            "--cursor",
            "opaque",
            "--published",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [
        (
            "list",
            {
                "project_id": "41",
                "search_filter": "wind",
                "order_by": AppOrderField.UPDATED_AT,
                "order": SortOrder.DESC,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
                "is_published": True,
            },
        )
    ]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "apps": [
                {
                    "app_id": "101",
                    "project_id": "41",
                    "name": "Wind tunnel",
                    "display_route": "engineering / airfoil / Wind tunnel",
                    "route": "/engineering/airfoil/101",
                    "visibility": "PRIVATE",
                    "app_type": "REGULAR",
                }
            ],
            "page": {"offset": 2, "count": 1, "cursor": "next"},
        },
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_create_uses_api_key_and_emits_structured_app() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "app",
            "create",
            "41",
            "--template-id",
            "9",
            "--name",
            "Agent app",
            "--description",
            "Created by automation",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [
        (
            "create",
            {
                "project_id": "41",
                "template_id": "9",
                "name": "Agent app",
                "description": "Created by automation",
            },
        )
    ]
    assert _json(result)["data"]["app"] == _app_detail().model_dump(mode="json")
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_update_uses_api_key_and_emits_exact_app_id() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "app",
            "update",
            "101",
            "--name",
            "Updated app",
            "--description",
            "Updated by automation",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [
        (
            "update",
            {
                "app_id": "101",
                "name": "Updated app",
                "description": "Updated by automation",
            },
        )
    ]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"app_id": "101"},
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_delete_uses_api_key_and_emits_exact_app_id() -> None:
    result = runner.invoke(
        cli_module.app,
        ["app", "delete", "101", "--yes"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [("delete", {"app_id": "101"})]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"app_id": "101"},
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_delete_without_confirmation_fails_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["app", "delete", "101"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeApps.calls == []
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": False,
        "data": None,
        "error": {
            "code": "CONFIGURATION_ERROR",
            "message": "App deletion requires --yes.",
            "retryable": False,
        },
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_get_uses_api_key() -> None:
    result = runner.invoke(
        cli_module.app,
        ["app", "get", "101"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.test",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [("get", {"app_id": "101"})]
    assert _json(result)["data"]["app"]["description"] == "Transient CFD study"
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_get_by_route_passes_exact_route() -> None:
    result = runner.invoke(
        cli_module.app,
        ["app", "get-by-route", "/engineering/airfoil/101"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeApps.calls == [("get_by_route", {"route": "/engineering/airfoil/101"})]


def test_api_key_read_uses_hosted_origin_by_default_and_redacts_key() -> None:
    result = runner.invoke(
        cli_module.app,
        ["app", "get", "101"],
        env={"DICEHUB_API_KEY": "sentinel-api-key"},
    )

    assert result.exit_code == 0
    assert _FakeClient.constructions == [
        {
            "base_url": "https://dicehub.com",
            "api_key": "sentinel-api-key",
            "session_cookie": None,
        }
    ]
    assert _FakeApps.calls == [("get", {"app_id": "101"})]
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_text_output_escapes_untrusted_app_fields() -> None:
    _FakeApps.detail = _app_detail(name="unsafe\nname")
    result = runner.invoke(
        cli_module.app,
        ["app", "get", "101", "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    assert "unsafe\\nname" in result.stdout


@pytest.mark.parametrize(
    "command",
    ["create", "update", "delete", "list", "get", "get-by-route"],
)
def test_app_help_exposes_no_credential_or_url_options(command: str) -> None:
    result = runner.invoke(cli_module.app, ["app", command, "--help"])

    assert result.exit_code == 0
    assert "--api-key" not in result.stdout
    assert "--session-cookie" not in result.stdout
    assert "--url" not in result.stdout
