from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dicehub.errors import ConfigurationError


@dataclass(frozen=True)
class MemberAddSelectors:
    namespace_id: str | None
    namespace_route: str | None
    member_id: str | None
    username: str | None
    team_route: str | None
    role_id: str | None
    role_name: str | None

    @property
    def uses_human_readable_value(self) -> bool:
        return any(
            value is not None
            for value in (
                self.namespace_route,
                self.username,
                self.team_route,
                self.role_name,
            )
        )


@dataclass(frozen=True)
class ResolvedMemberAdd:
    namespace_id: str
    member_id: str
    role_id: str
    member_type: str | None
    namespace_route: str | None
    username: str | None
    team_route: str | None
    role_name: str | None
    uses_human_readable_value: bool


def validated_member_add_selectors(
    *,
    namespace_label: str,
    namespace_id: str | None,
    namespace_route: str | None,
    member_id: str | None,
    username: str | None,
    team_route: str | None,
    role_id: str | None,
    role_name: str | None,
) -> MemberAddSelectors:
    _require_exactly_one(
        (namespace_id, namespace_route),
        f"{namespace_label} member creation requires exactly one target ID or route.",
    )
    _require_exactly_one(
        (member_id, username, team_route),
        f"{namespace_label} member creation requires exactly one member ID, username, "
        "or team route.",
    )
    _require_exactly_one(
        (role_id, role_name),
        f"{namespace_label} member creation requires exactly one role ID or role name.",
    )
    return MemberAddSelectors(
        namespace_id=namespace_id,
        namespace_route=namespace_route,
        member_id=member_id,
        username=username,
        team_route=team_route,
        role_id=role_id,
        role_name=role_name,
    )


def resolve_member_add(
    *,
    client: Any,
    selectors: MemberAddSelectors,
    resolve_namespace: Callable[[Any, str], tuple[str, str]],
    resolve_role: Callable[[Any, str, str], tuple[str, str]],
) -> ResolvedMemberAdd:
    namespace_id = selectors.namespace_id
    namespace_route = None
    if selectors.namespace_route is not None:
        namespace_id, namespace_route = resolve_namespace(client, selectors.namespace_route)
    if namespace_id is None:
        raise ConfigurationError("The membership target ID is missing.")

    member_id = selectors.member_id
    member_type = None
    username = None
    team_route = None
    if selectors.username is not None:
        candidate = client.users.resolve_membership_candidate(
            namespace_id=namespace_id,
            username=selectors.username,
        )
        member_id = candidate.user_id
        member_type = "USER"
        username = candidate.username
    elif selectors.team_route is not None:
        team = client.teams.get_by_route(route=selectors.team_route)
        member_id = team.team_id
        member_type = "TEAM"
        team_route = team.route
    if member_id is None:
        raise ConfigurationError("The membership member ID is missing.")

    role_id = selectors.role_id
    role_name = None
    if selectors.role_name is not None:
        role_id, role_name = resolve_role(client, namespace_id, selectors.role_name)
    if role_id is None:
        raise ConfigurationError("The membership role ID is missing.")

    return ResolvedMemberAdd(
        namespace_id=namespace_id,
        member_id=member_id,
        role_id=role_id,
        member_type=member_type,
        namespace_route=namespace_route,
        username=username,
        team_route=team_route,
        role_name=role_name,
        uses_human_readable_value=selectors.uses_human_readable_value,
    )


def member_add_data(namespace_key: str, resolved: ResolvedMemberAdd) -> dict[str, object]:
    data: dict[str, object] = {
        namespace_key: resolved.namespace_id,
        "member_id": resolved.member_id,
    }
    if not resolved.uses_human_readable_value:
        return data
    data.update(
        {
            "role_id": resolved.role_id,
            "member_type": resolved.member_type,
            "resolved": {
                "namespace_route": resolved.namespace_route,
                "username": resolved.username,
                "team_route": resolved.team_route,
                "role_name": resolved.role_name,
            },
        }
    )
    return data


def _require_exactly_one(values: tuple[str | None, ...], message: str) -> None:
    if sum(value is not None for value in values) != 1:
        raise ConfigurationError(message)
