from __future__ import annotations

import json
from types import SimpleNamespace, TracebackType
from typing import Any, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import cli as cli_module
from dicehub.cli.commands import app_members, group_members, project_members
from dicehub.errors import SelectorResolutionError
from dicehub.groups.models import MembershipVisibility

runner = CliRunner()


class _FakeGroups:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def get_by_route(self, *, route: str) -> Any:
        self.calls.append(("group_route", {"route": route}))
        return SimpleNamespace(group_id="73", route="/research/automation")

    def get_role_by_name(self, *, group_id: str, name: str) -> Any:
        self.calls.append(("group_role", {"group_id": group_id, "name": name}))
        return SimpleNamespace(role_id="3", name="DEVELOPER")

    def add_member(
        self,
        *,
        group_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility,
    ) -> None:
        self.calls.append(
            (
                "group_add",
                {
                    "group_id": group_id,
                    "member_id": member_id,
                    "role_id": role_id,
                    "visibility": visibility,
                },
            )
        )


class _FakeProjects:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def get_by_route(self, *, route: str) -> Any:
        self.calls.append(("project_route", {"route": route}))
        return SimpleNamespace(project_id="41", route="/ros/update_august")

    def get_role_by_name(self, *, project_id: str, name: str) -> Any:
        self.calls.append(("project_role", {"project_id": project_id, "name": name}))
        return SimpleNamespace(role_id="4", name="REPORTER")

    def add_member(
        self,
        *,
        project_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility,
    ) -> None:
        self.calls.append(
            (
                "project_add",
                {
                    "project_id": project_id,
                    "member_id": member_id,
                    "role_id": role_id,
                    "visibility": visibility,
                },
            )
        )


class _FakeApps:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def get_by_route(self, *, route: str) -> Any:
        self.calls.append(("app_route", {"route": route}))
        return SimpleNamespace(app_id="101", route="/ros/update_august/wind_tunnel")

    def get_role_by_name(self, *, app_id: str, name: str) -> Any:
        self.calls.append(("app_role", {"app_id": app_id, "name": name}))
        return SimpleNamespace(role_id="5", name="EDITOR")

    def add_member(
        self,
        *,
        app_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility,
    ) -> None:
        self.calls.append(
            (
                "app_add",
                {
                    "app_id": app_id,
                    "member_id": member_id,
                    "role_id": role_id,
                    "visibility": visibility,
                },
            )
        )


class _FakeUsers:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []
    error: ClassVar[SelectorResolutionError | None] = None

    def resolve_membership_candidate(self, *, namespace_id: str, username: str) -> Any:
        self.calls.append(("user", {"namespace_id": namespace_id, "username": username}))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(user_id="7", username="ada")


class _FakeTeams:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def get_by_route(self, *, route: str) -> Any:
        self.calls.append(("team", {"route": route}))
        return SimpleNamespace(team_id="8", route="/research/solvers")


class _FakeClient:
    apps = _FakeApps()
    groups = _FakeGroups()
    projects = _FakeProjects()
    users = _FakeUsers()
    teams = _FakeTeams()
    constructions: ClassVar[int] = 0

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
    ) -> None:
        type(self).constructions += 1

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
    _FakeGroups.calls = []
    _FakeProjects.calls = []
    _FakeUsers.calls = []
    _FakeUsers.error = None
    _FakeTeams.calls = []
    _FakeClient.constructions = 0
    monkeypatch.setattr(app_members, "Client", _FakeClient)
    monkeypatch.setattr(group_members, "Client", _FakeClient)
    monkeypatch.setattr(project_members, "Client", _FakeClient)


def _environment() -> dict[str, str]:
    return {
        "DICEHUB_API_KEY": "test-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    return cast(dict[str, Any], json.loads(result.stdout))


def test_group_add_resolves_exact_username_and_role_before_id_mutation() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "group",
            "members",
            "add",
            "--group-route",
            "/research/automation",
            "--username",
            "Ada",
            "--role",
            "DEVELOPER",
            "--yes",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0
    assert _FakeGroups.calls == [
        ("group_route", {"route": "/research/automation"}),
        ("group_role", {"group_id": "73", "name": "DEVELOPER"}),
        (
            "group_add",
            {
                "group_id": "73",
                "member_id": "7",
                "role_id": "3",
                "visibility": MembershipVisibility.PRIVATE,
            },
        ),
    ]
    assert _FakeUsers.calls == [("user", {"namespace_id": "73", "username": "Ada"})]
    assert _json(result)["data"] == {
        "group_id": "73",
        "member_id": "7",
        "role_id": "3",
        "member_type": "USER",
        "resolved": {
            "namespace_route": "/research/automation",
            "username": "ada",
            "team_route": None,
            "role_name": "DEVELOPER",
        },
    }


def test_project_add_resolves_exact_team_route_and_role_before_id_mutation() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "project",
            "members",
            "add",
            "--project-route",
            "/ros/update_august",
            "--team-route",
            "/research/solvers",
            "--role-name",
            "REPORTER",
            "--yes",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0
    assert _FakeProjects.calls[-1] == (
        "project_add",
        {
            "project_id": "41",
            "member_id": "8",
            "role_id": "4",
            "visibility": MembershipVisibility.PRIVATE,
        },
    )
    assert _FakeTeams.calls == [("team", {"route": "/research/solvers"})]
    assert _json(result)["data"] == {
        "project_id": "41",
        "member_id": "8",
        "role_id": "4",
        "member_type": "TEAM",
        "resolved": {
            "namespace_route": "/ros/update_august",
            "username": None,
            "team_route": "/research/solvers",
            "role_name": "REPORTER",
        },
    }


def test_app_add_resolves_exact_username_and_role_before_id_mutation() -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "app",
            "members",
            "add",
            "--app-route",
            "/ros/update_august/wind_tunnel",
            "--username",
            "Ada",
            "--role",
            "EDITOR",
            "--yes",
        ],
        env=_environment(),
    )

    assert result.exit_code == 0
    assert _FakeApps.calls == [
        ("app_route", {"route": "/ros/update_august/wind_tunnel"}),
        ("app_role", {"app_id": "101", "name": "EDITOR"}),
        (
            "app_add",
            {
                "app_id": "101",
                "member_id": "7",
                "role_id": "5",
                "visibility": MembershipVisibility.PRIVATE,
            },
        ),
    ]
    assert _FakeUsers.calls == [("user", {"namespace_id": "101", "username": "Ada"})]
    assert _json(result)["data"] == {
        "app_id": "101",
        "member_id": "7",
        "role_id": "5",
        "member_type": "USER",
        "resolved": {
            "namespace_route": "/ros/update_august/wind_tunnel",
            "username": "ada",
            "team_route": None,
            "role_name": "EDITOR",
        },
    }


def test_project_id_add_keeps_compact_id_output() -> None:
    result = runner.invoke(
        cli_module.app,
        ["project", "members", "add", "41", "7", "--role-id", "3", "--yes"],
        env=_environment(),
    )

    assert result.exit_code == 0
    assert _json(result)["data"] == {"project_id": "41", "member_id": "7"}


@pytest.mark.parametrize(
    "arguments",
    [
        ["73", "7", "--group-route", "/research/automation", "--role-id", "3", "--yes"],
        ["73", "7", "--username", "ada", "--role-id", "3", "--yes"],
        ["73", "7", "--role-id", "3", "--role", "DEVELOPER", "--yes"],
        ["73", "7", "--role-id", "3"],
    ],
)
def test_invalid_or_unconfirmed_group_add_stops_before_client(arguments: list[str]) -> None:
    result = runner.invoke(
        cli_module.app,
        ["group", "members", "add", *arguments],
        env=_environment(),
    )

    assert result.exit_code == 2
    assert _FakeClient.constructions == 0
    assert _json(result)["error"]["code"] == "CONFIGURATION_ERROR"


def test_selector_failure_does_not_send_member_mutation() -> None:
    _FakeUsers.error = SelectorResolutionError(selector="username", reason="NOT_FOUND")

    result = runner.invoke(
        cli_module.app,
        [
            "group",
            "members",
            "add",
            "73",
            "--username",
            "missing",
            "--role-id",
            "3",
            "--yes",
        ],
        env=_environment(),
    )

    assert result.exit_code == 4
    assert all(call[0] != "group_add" for call in _FakeGroups.calls)
    assert _json(result)["error"] == {
        "code": "SELECTOR_RESOLUTION_ERROR",
        "message": "The exact membership selector did not resolve to one authorized result.",
        "retryable": False,
        "selector": "username",
        "reason": "NOT_FOUND",
    }
