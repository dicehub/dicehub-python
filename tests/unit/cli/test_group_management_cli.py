from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO, ClassVar, cast

import pytest
from typer.testing import CliRunner

from dicehub import (
    GroupDetail,
    GroupMemberTeam,
    GroupMemberUser,
    GroupRole,
    GroupTeamMembership,
    GroupTeamMembershipPage,
    GroupUserMembership,
    GroupUserMembershipPage,
    GroupVisibility,
    MembershipVisibility,
)
from dicehub import cli as cli_module
from dicehub.cli.commands import group as group_commands
from dicehub.cli.commands import group_avatar as avatar_commands
from dicehub.cli.commands import group_members as member_commands

runner = CliRunner()


def _group() -> GroupDetail:
    return GroupDetail(
        group_id="73",
        parent_id="42",
        name="Automation",
        display_route="Research / Automation",
        route="/research/automation",
        visibility=GroupVisibility.PRIVATE,
        has_children=False,
        description="Managed by the SDK",
        avatar_url=None,
    )


def _user_page() -> GroupUserMembershipPage:
    return GroupUserMembershipPage(
        memberships=(
            GroupUserMembership(
                membership_id="901",
                member_id="7",
                namespace_id="73",
                role_id="3",
                visibility=MembershipVisibility.PRIVATE,
                inherited=False,
                user=GroupMemberUser(
                    user_id="7",
                    first_name="Ada",
                    last_name="Lovelace",
                    username="ada",
                    avatar_url=None,
                ),
            ),
        ),
        offset=2,
        count=1,
        cursor="next",
    )


def _team_page() -> GroupTeamMembershipPage:
    return GroupTeamMembershipPage(
        memberships=(
            GroupTeamMembership(
                membership_id="902",
                member_id="8",
                namespace_id="73",
                role_id="4",
                visibility=MembershipVisibility.PUBLIC,
                inherited=True,
                team=GroupMemberTeam(
                    team_id="8",
                    name="Solvers",
                    route="/research/solvers",
                    avatar_url=None,
                ),
            ),
        ),
        offset=0,
        count=1,
        cursor="team-next",
    )


class _FakeGroups:
    calls: ClassVar[list[tuple[str, dict[str, object]]]] = []

    def create(
        self,
        *,
        name: str,
        slug: str,
        parent_id: str | None = None,
        description: str | None = None,
        visibility: GroupVisibility = GroupVisibility.PRIVATE,
    ) -> GroupDetail:
        self.calls.append(
            (
                "create",
                {
                    "name": name,
                    "slug": slug,
                    "parent_id": parent_id,
                    "description": description,
                    "visibility": visibility,
                },
            )
        )
        return _group()

    def delete(self, *, group_id: str) -> None:
        self.calls.append(("delete", {"group_id": group_id}))

    def move(self, *, group_id: str, to_group_id: str) -> None:
        self.calls.append(("move", {"group_id": group_id, "to_group_id": to_group_id}))

    def list_roles(self, *, group_id: str) -> tuple[GroupRole, ...]:
        self.calls.append(("list_roles", {"group_id": group_id}))
        return (GroupRole(role_id="3", name="MAINTAINER"),)

    def set_avatar(self, *, group_id: str, source: BinaryIO) -> None:
        self.calls.append(("set_avatar", {"group_id": group_id, "content": source.read()}))

    def clear_avatar(self, *, group_id: str) -> None:
        self.calls.append(("clear_avatar", {"group_id": group_id}))

    def list_user_members(
        self,
        *,
        group_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupUserMembershipPage:
        self.calls.append(
            (
                "list_user_members",
                {
                    "group_id": group_id,
                    "include_inherited": include_inherited,
                    "deduplicate": deduplicate,
                    "search_filter": search_filter,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return _user_page()

    def list_team_members(
        self,
        *,
        group_id: str,
        include_inherited: bool = True,
        deduplicate: bool = False,
        search_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> GroupTeamMembershipPage:
        self.calls.append(
            (
                "list_team_members",
                {
                    "group_id": group_id,
                    "include_inherited": include_inherited,
                    "deduplicate": deduplicate,
                    "search_filter": search_filter,
                    "offset": offset,
                    "limit": limit,
                    "cursor": cursor,
                },
            )
        )
        return _team_page()

    def add_member(
        self,
        *,
        group_id: str,
        member_id: str,
        role_id: str,
        visibility: MembershipVisibility = MembershipVisibility.PRIVATE,
    ) -> None:
        self.calls.append(
            (
                "add_member",
                {
                    "group_id": group_id,
                    "member_id": member_id,
                    "role_id": role_id,
                    "visibility": visibility,
                },
            )
        )

    def update_member(
        self,
        *,
        group_id: str,
        member_id: str,
        role_id: str | None = None,
        visibility: MembershipVisibility | None = None,
    ) -> None:
        self.calls.append(
            (
                "update_member",
                {
                    "group_id": group_id,
                    "member_id": member_id,
                    "role_id": role_id,
                    "visibility": visibility,
                },
            )
        )

    def remove_member(self, *, group_id: str, member_id: str) -> None:
        self.calls.append(("remove_member", {"group_id": group_id, "member_id": member_id}))


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
    _FakeClient.constructions = []
    for name in ("DICEHUB_API_KEY", "DICEHUB_SESSION_COOKIE", "DICEHUB_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(group_commands, "Client", _FakeClient)
    monkeypatch.setattr(avatar_commands, "Client", _FakeClient)
    monkeypatch.setattr(member_commands, "Client", _FakeClient)


def _json(result: Any) -> dict[str, Any]:
    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _api_key_env() -> dict[str, str]:
    return {
        "DICEHUB_API_KEY": "sentinel-api-key",
        "DICEHUB_URL": "https://dicehub.test",
    }


def _session_env() -> dict[str, str]:
    return {
        "DICEHUB_SESSION_COOKIE": "sentinel-session-cookie",
        "DICEHUB_URL": "https://dicehub.test",
    }


@pytest.mark.parametrize(
    ("arguments", "environment", "expected_parent", "credential"),
    [
        (["--name", "Automation", "--slug", "automation"], _session_env(), None, "session"),
        (
            ["--name", "Automation", "--slug", "automation", "--parent-id", "42"],
            _api_key_env(),
            "42",
            "api-key",
        ),
    ],
)
def test_create_selects_identity_from_destination(
    arguments: list[str],
    environment: dict[str, str],
    expected_parent: str | None,
    credential: str,
) -> None:
    result = runner.invoke(cli_module.app, ["group", "create", *arguments], env=environment)

    assert result.exit_code == 0
    assert _FakeGroups.calls[0][0] == "create"
    assert _FakeGroups.calls[0][1]["parent_id"] == expected_parent
    assert _FakeClient.constructions[0]["api_key"] == (
        "sentinel-api-key" if credential == "api-key" else None
    )
    assert _FakeClient.constructions[0]["session_cookie"] == (
        "sentinel-session-cookie" if credential == "session" else None
    )
    assert _json(result)["data"]["group"]["group_id"] == "73"


@pytest.mark.parametrize(
    ("arguments", "environment", "expected_call", "expected_data"),
    [
        (
            ["delete", "73", "--yes"],
            _api_key_env(),
            ("delete", {"group_id": "73"}),
            {"group_id": "73"},
        ),
        (
            ["move", "73", "42", "--yes"],
            _session_env(),
            ("move", {"group_id": "73", "to_group_id": "42"}),
            {"group_id": "73", "to_group_id": "42"},
        ),
        (["roles", "73"], _api_key_env(), ("list_roles", {"group_id": "73"}), None),
    ],
)
def test_lifecycle_commands_use_expected_identity_and_service(
    arguments: list[str],
    environment: dict[str, str],
    expected_call: tuple[str, dict[str, object]],
    expected_data: dict[str, object] | None,
) -> None:
    result = runner.invoke(cli_module.app, ["group", *arguments], env=environment)

    assert result.exit_code == 0
    assert _FakeGroups.calls == [expected_call]
    payload = _json(result)
    if expected_data is None:
        assert payload["data"]["roles"] == [{"role_id": "3", "name": "MAINTAINER"}]
    else:
        assert payload["data"] == expected_data


def test_avatar_set_and_clear_use_api_key(tmp_path: Path) -> None:
    image = b"\x89PNG\r\n\x1a\nimage"
    source = tmp_path / "avatar.png"
    source.write_bytes(image)

    set_result = runner.invoke(
        cli_module.app,
        ["group", "avatar", "set", "73", str(source), "--yes"],
        env=_api_key_env(),
    )
    clear_result = runner.invoke(
        cli_module.app,
        ["group", "avatar", "clear", "73", "--yes"],
        env=_api_key_env(),
    )

    assert set_result.exit_code == clear_result.exit_code == 0
    assert _FakeGroups.calls == [
        ("set_avatar", {"group_id": "73", "content": image}),
        ("clear_avatar", {"group_id": "73"}),
    ]
    assert _json(set_result)["data"] == {"group_id": "73"}
    assert _json(clear_result)["data"] == {"group_id": "73"}


def test_member_lists_emit_typed_pages() -> None:
    users = runner.invoke(
        cli_module.app,
        [
            "group",
            "members",
            "list-users",
            "73",
            "--direct-only",
            "--deduplicate",
            "--search",
            "ada",
            "--offset",
            "2",
            "--limit",
            "5",
            "--cursor",
            "opaque",
        ],
        env=_api_key_env(),
    )
    teams = runner.invoke(
        cli_module.app,
        ["group", "members", "list-teams", "73"],
        env=_api_key_env(),
    )

    assert users.exit_code == teams.exit_code == 0
    assert _FakeGroups.calls[0] == (
        "list_user_members",
        {
            "group_id": "73",
            "include_inherited": False,
            "deduplicate": True,
            "search_filter": "ada",
            "offset": 2,
            "limit": 5,
            "cursor": "opaque",
        },
    )
    assert _FakeGroups.calls[1][0] == "list_team_members"
    assert _json(users)["data"]["memberships"][0]["user"]["username"] == "ada"
    assert _json(teams)["data"]["memberships"][0]["team"]["team_id"] == "8"


@pytest.mark.parametrize(
    ("arguments", "expected_call"),
    [
        (
            ["add", "73", "7", "--role-id", "3", "--visibility", "public", "--yes"],
            (
                "add_member",
                {
                    "group_id": "73",
                    "member_id": "7",
                    "role_id": "3",
                    "visibility": MembershipVisibility.PUBLIC,
                },
            ),
        ),
        (
            ["update", "73", "7", "--role-id", "4", "--visibility", "hidden", "--yes"],
            (
                "update_member",
                {
                    "group_id": "73",
                    "member_id": "7",
                    "role_id": "4",
                    "visibility": MembershipVisibility.HIDDEN,
                },
            ),
        ),
        (
            ["remove", "73", "7", "--yes"],
            ("remove_member", {"group_id": "73", "member_id": "7"}),
        ),
    ],
)
def test_member_mutations_require_explicit_values(
    arguments: list[str],
    expected_call: tuple[str, dict[str, object]],
) -> None:
    result = runner.invoke(
        cli_module.app,
        ["group", "members", *arguments],
        env=_api_key_env(),
    )

    assert result.exit_code == 0
    assert _FakeGroups.calls == [expected_call]
    assert _json(result)["data"] == {"group_id": "73", "member_id": "7"}


@pytest.mark.parametrize(
    "arguments",
    [
        ["delete", "73"],
        ["move", "73", "42"],
        ["avatar", "clear", "73"],
        ["members", "add", "73", "7", "--role-id", "3"],
        ["members", "update", "73", "7", "--role-id", "4"],
        ["members", "remove", "73", "7"],
    ],
)
def test_high_impact_commands_without_yes_stop_before_client(arguments: list[str]) -> None:
    result = runner.invoke(cli_module.app, ["group", *arguments], env=_api_key_env())

    assert result.exit_code == 2
    assert _FakeClient.constructions == []
    assert _FakeGroups.calls == []
    assert _json(result)["error"]["code"] == "CONFIGURATION_ERROR"
