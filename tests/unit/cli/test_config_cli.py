from __future__ import annotations

import json
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import Config, ConfigPage
from dicehub import cli as cli_module
from dicehub.cli.commands import config as config_commands
from dicehub.projects import SortOrder

runner = CliRunner()


def _config() -> Config:
    return Config(
        config_id="301",
        app_id="101",
        config_internal_id="7",
        name="Baseline",
        description="Reference setup",
        is_default=True,
        template_version="v13",
        updating=False,
    )


class _FakeConfigs:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def list(
        self,
        *,
        app_id: str,
        search_filter: str | None = None,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConfigPage:
        self.calls.append(
            (
                "list",
                {
                    "app_id": app_id,
                    "search_filter": search_filter,
                    "order": order,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return ConfigPage(configs=(_config(),), offset=offset, count=1, cursor="next")

    def get(self, *, config_id: str) -> Config:
        self.calls.append(("get", {"config_id": config_id}))
        return _config()

    def create(
        self,
        *,
        app_id: str,
        source_config_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Config:
        self.calls.append(
            (
                "create",
                {
                    "app_id": app_id,
                    "source_config_id": source_config_id,
                    "name": name,
                    "description": description,
                },
            )
        )
        return _config().model_copy(update={"is_default": False, "name": name or "Baseline"})

    def delete(self, *, config_id: str) -> None:
        self.calls.append(("delete", {"config_id": config_id}))


class _FakeClient:
    configs = _FakeConfigs()
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
    _FakeConfigs.calls = []
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(config_commands, "Client", _FakeClient)


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
            "config",
            "list",
            "101",
            "--search",
            "base",
            "--order",
            "desc",
            "--offset",
            "2",
            "--limit",
            "5",
            "--cursor",
            "opaque",
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
    assert _FakeConfigs.calls == [
        (
            "list",
            {
                "app_id": "101",
                "search_filter": "base",
                "order": SortOrder.DESC,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
            },
        )
    ]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {
            "configs": [_config().model_dump(mode="json")],
            "page": {"offset": 2, "count": 1, "cursor": "next"},
        },
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_get_uses_api_key_and_emits_structured_config() -> None:
    result = runner.invoke(
        cli_module.app,
        ["config", "get", "301"],
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
    assert _FakeConfigs.calls == [("get", {"config_id": "301"})]
    assert _json(result)["data"] == {"config": _config().model_dump(mode="json")}
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_create_uses_api_key_and_emits_structured_config() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "config",
            "create",
            "101",
            "--source-config-id",
            "301",
            "--name",
            "Agent baseline",
            "--description",
            "Created by automation",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeConfigs.calls == [
        (
            "create",
            {
                "app_id": "101",
                "source_config_id": "301",
                "name": "Agent baseline",
                "description": "Created by automation",
            },
        )
    ]
    assert _json(result)["data"]["config"]["name"] == "Agent baseline"
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_delete_uses_api_key_and_emits_exact_config_id() -> None:
    result = runner.invoke(
        cli_module.app,
        ["config", "delete", "301", "--yes"],
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
    assert _FakeConfigs.calls == [("delete", {"config_id": "301"})]
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"config_id": "301"},
        "error": None,
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_delete_rejects_session_authentication_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["config", "delete", "301", "--yes"],
        env={"DICEHUB_SESSION_COOKIE": "sentinel-session"},
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeConfigs.calls == []
    assert _json(result)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "DICEHUB_SESSION_COOKIE is not supported for this command; use DICEHUB_API_KEY.",
        "retryable": False,
    }
    assert "sentinel-session" not in result.stdout + result.stderr


def test_delete_without_confirmation_fails_before_client_construction() -> None:
    result = runner.invoke(
        cli_module.app,
        ["config", "delete", "301"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeConfigs.calls == []
    assert _json(result) == {
        "schema_version": "dicehub.cli/v1",
        "ok": False,
        "data": None,
        "error": {
            "code": "CONFIGURATION_ERROR",
            "message": "Config deletion requires --yes.",
            "retryable": False,
        },
    }
    assert "sentinel-api-key" not in result.stdout + result.stderr + repr(result.exception)


def test_text_output_is_tab_separated() -> None:
    result = runner.invoke(
        cli_module.app,
        ["config", "get", "301", "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout == "301\t101\tBaseline\tTrue\n"


def test_config_help_exposes_metadata_and_content_operations() -> None:
    result = runner.invoke(cli_module.app, ["config", "--help"])

    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "get" in result.stdout
    assert "create" in result.stdout
    assert "update" in result.stdout
    assert "content" in result.stdout
    assert "delete" in result.stdout
