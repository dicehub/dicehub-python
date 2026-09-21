from __future__ import annotations

import json
from types import TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import APIError, Group, GroupDetail, GroupPage, GroupVisibility
from dicehub import cli as cli_module
from dicehub.cli.commands import group as group_commands
from dicehub.groups import GroupOrderField
from dicehub.projects import SortOrder

runner = CliRunner()


def _group(*, name: str = "Research") -> Group:
    return Group(
        group_id="73",
        parent_id="42",
        name=name,
        display_route="dicehub / Research",
        route="/dicehub/research",
        visibility=GroupVisibility.PRIVATE,
        has_children=True,
    )


def _group_detail(*, name: str = "Research") -> GroupDetail:
    return GroupDetail(
        **_group(name=name).model_dump(),
        description="Simulation research group.",
        avatar_url=None,
    )


class _FakeGroups:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[Exception | None] = None
    result: ClassVar[GroupDetail] = _group_detail()

    def _record(self, name: str, values: dict[str, object]) -> None:
        self.calls.append((name, values))
        if self.error is not None:
            raise self.error

    def list(
        self,
        *,
        user_id: str | None = None,
        parent_id: str | None = None,
        search_filter: str | None = None,
        order_by: GroupOrderField = GroupOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupPage:
        self._record(
            "list",
            {
                "user_id": user_id,
                "parent_id": parent_id,
                "search_filter": search_filter,
                "order_by": order_by,
                "order": order,
                "offset": offset,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return GroupPage(groups=(_group(),), offset=offset, count=1, cursor="next")

    def get(self, *, group_id: str) -> GroupDetail:
        self._record("get", {"group_id": group_id})
        return self.result

    def get_by_route(self, *, route: str) -> GroupDetail:
        self._record("get_by_route", {"route": route})
        return self.result

    def update(
        self,
        *,
        group_id: str,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        visibility: GroupVisibility | None = None,
    ) -> None:
        self._record(
            "update",
            {
                "group_id": group_id,
                "name": name,
                "slug": slug,
                "description": description,
                "visibility": visibility,
            },
        )


class _FakeClient:
    groups = _FakeGroups()
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
    _FakeGroups.calls = []
    _FakeGroups.error = None
    _FakeGroups.result = _group_detail()
    _FakeClient.constructions = []
    monkeypatch.delenv("DICEHUB_API_KEY", raising=False)
    monkeypatch.delenv("DICEHUB_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("DICEHUB_URL", raising=False)
    monkeypatch.setattr(group_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def test_list_emits_structured_page_and_passes_filters() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "group",
            "list",
            "--user-id",
            "7",
            "--parent-id",
            "42",
            "--search",
            "research",
            "--order-by",
            "updated_at",
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
    assert _FakeGroups.calls == [
        (
            "list",
            {
                "user_id": "7",
                "parent_id": "42",
                "search_filter": "research",
                "order_by": GroupOrderField.UPDATED_AT,
                "order": SortOrder.DESC,
                "offset": 2,
                "limit": 5,
                "cursor": "opaque",
            },
        )
    ]
    payload = _json(result)
    assert payload["schema_version"] == "dicehub.cli/v1"
    assert payload["ok"] is True
    assert payload["data"]["page"] == {"offset": 2, "count": 1, "cursor": "next"}
    assert payload["data"]["groups"][0]["group_id"] == "73"
    assert "sentinel-api-key" not in result.stdout


def test_get_by_id_and_route_use_exact_values() -> None:
    env = {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }

    by_id = runner.invoke(cli_module.app, ["group", "get", "73"], env=env)
    by_route = runner.invoke(
        cli_module.app,
        ["group", "get-by-route", "/dicehub/research"],
        env=env,
    )

    assert by_id.exit_code == 0
    assert by_route.exit_code == 0
    assert _FakeGroups.calls == [
        ("get", {"group_id": "73"}),
        ("get_by_route", {"route": "/dicehub/research"}),
    ]
    assert _json(by_id)["data"]["group"]["description"] == "Simulation research group."
    assert _json(by_route)["data"]["group"]["route"] == "/dicehub/research"


def test_text_output_escapes_untrusted_control_characters() -> None:
    _FakeGroups.result = _group_detail(name="Research\nunsafe\tname")

    result = runner.invoke(
        cli_module.app,
        ["group", "get", "73", "--output", "text"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
    assert "Research\\nunsafe\\tname" in result.stdout


def test_operational_error_uses_stable_json_envelope() -> None:
    _FakeGroups.error = APIError("dicehub rejected the operation.")

    result = runner.invoke(
        cli_module.app,
        ["group", "list"],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 4
    payload = _json(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "API_ERROR"
    assert payload["error"]["retryable"] is False


def test_update_uses_api_key_without_exposing_it() -> None:
    result = runner.invoke(
        cli_module.app,
        ["group", "update", "73", "--description", "Updated by agent"],
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
    assert _FakeGroups.calls == [
        (
            "update",
            {
                "group_id": "73",
                "name": None,
                "slug": None,
                "description": "Updated by agent",
                "visibility": None,
            },
        )
    ]
    assert _json(result)["data"] == {"group_id": "73"}
    assert "sentinel-api-key" not in result.stdout + result.stderr


def test_update_passes_all_fields_after_confirmation() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "group",
            "update",
            "73",
            "--name",
            "Applied Research",
            "--slug",
            "applied-research",
            "--description",
            "",
            "--visibility",
            "internal",
            "--yes",
        ],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 0
    assert _FakeGroups.calls == [
        (
            "update",
            {
                "group_id": "73",
                "name": "Applied Research",
                "slug": "applied-research",
                "description": "",
                "visibility": GroupVisibility.INTERNAL,
            },
        )
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        ["update", "73", "--slug", "new-route"],
        ["update", "73", "--visibility", "public"],
    ],
)
def test_route_or_visibility_update_without_yes_refuses_before_client(
    arguments: list[str],
) -> None:
    result = runner.invoke(
        cli_module.app,
        ["group", *arguments],
        env={
            "DICEHUB_API_KEY": "sentinel-api-key",
            "DICEHUB_URL": "https://dicehub.test",
        },
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeGroups.calls == []
    assert _json(result)["error"] == {
        "code": "CONFIGURATION_ERROR",
        "message": "Group slug or visibility update requires --yes.",
        "retryable": False,
    }


@pytest.mark.parametrize("command", ["list", "get", "get-by-route", "update"])
def test_group_command_help(command: str) -> None:
    result = runner.invoke(cli_module.app, ["group", command, "--help"])

    assert result.exit_code == 0
    assert result.stderr == ""
