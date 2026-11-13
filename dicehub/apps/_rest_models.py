"""Explicit REST v2 response representations."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime

from dicehub._core.rest_models import WireModel, WirePage


class AppSummary(WireModel):
    app_id: str
    project_id: str
    name: str
    route: str | None
    display_route: str
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"] | None
    app_type: Literal["REGULAR", "MODEL", "PREVIEW"] | None


class AppDetail(WireModel):
    app_id: str
    project_id: str
    template_id: str | None
    template_name: str | None
    template_version: str | None
    template_slug: str | None
    community_app_id: str | None
    name: str
    description: str | None
    route: str | None
    display_route: str
    visibility: Literal["PRIVATE", "INTERNAL", "PUBLIC"] | None
    preview_url: str | None
    icon_path: str | None
    app_type: Literal["REGULAR", "MODEL", "PREVIEW"] | None
    updating: bool | None
    has_update_errors: bool | None
    active_runs_count: int | None
    failed_runs_count: int | None
    successful_runs_count: int | None
    active_studies_count: int | None
    failed_studies_count: int | None
    successful_studies_count: int | None
    partial_studies_count: int | None
    default_config_id: str | None
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None


class AppList(WirePage):
    items: tuple[AppSummary, ...]


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
