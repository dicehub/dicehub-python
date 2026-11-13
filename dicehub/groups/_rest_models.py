"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel, WirePage


class GroupSummary(WireModel):
    group_id: str
    parent_id: str | None
    name: str | None
    route: str | None
    display_route: str | None
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"] | None
    has_children: bool | None


class GroupDetail(WireModel):
    group_id: str
    name: str | None
    parent_id: str | None
    description: str | None
    route: str | None
    display_route: str | None
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"] | None
    avatar_url: str | None
    has_children: bool | None
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None


class GroupList(WirePage):
    items: tuple[GroupSummary, ...]


class Done(WireModel):
    succeeded: Literal[True]


class Role(WireModel):
    role_id: str
    name: str | None


class RoleList(WireModel):
    items: tuple[Role, ...]


class MemberUser(WireModel):
    user_id: str
    first_name: str | None
    last_name: str | None
    username: str
    avatar_url: str | None


class UserMembership(WireModel):
    membership_id: str
    member_id: str
    namespace_id: str
    role_id: str
    visibility: Literal["HIDDEN", "PRIVATE", "PUBLIC"]
    inherited: bool
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None
    user: MemberUser


class UserMembershipList(WirePage):
    items: tuple[UserMembership, ...]


class MemberTeam(WireModel):
    team_id: str
    name: str
    route: str
    avatar_url: str | None


class TeamMembership(WireModel):
    membership_id: str
    member_id: str
    namespace_id: str
    role_id: str
    visibility: Literal["HIDDEN", "PRIVATE", "PUBLIC"]
    inherited: bool
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None
    team: MemberTeam


class TeamMembershipList(WirePage):
    items: tuple[TeamMembership, ...]
