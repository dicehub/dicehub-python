from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from dicehub._core.membership import MembershipVisibility as MembershipVisibility


class AppVisibility(str, Enum):
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class AppType(str, Enum):
    REGULAR = "REGULAR"
    MODEL = "MODEL"
    PREVIEW = "PREVIEW"


class AppOrderField(str, Enum):
    APP_ID = "app_id"
    NAME = "name"
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"


class App(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    app_id: str = Field(min_length=1, max_length=256)
    project_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(min_length=1, max_length=16_384)
    route: str | None = Field(default=None, max_length=16_384)
    visibility: AppVisibility | None
    app_type: AppType | None


class AppDetail(App):
    description: str | None
    template_id: str | None = Field(default=None, max_length=256)
    template_name: str | None = Field(default=None, max_length=128)
    template_version: str | None = Field(default=None, max_length=256)
    template_slug: str | None = Field(default=None, max_length=256)
    icon_path: str | None = Field(default=None, max_length=16_384)
    preview_url: str | None = Field(default=None, max_length=16_384)


class AppPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: tuple[App, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class AppRole(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)


class AppMemberUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(min_length=1, max_length=256)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class AppMemberTeam(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class AppUserMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    user: AppMemberUser


class AppTeamMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    team: AppMemberTeam


class AppUserMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[AppUserMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class AppTeamMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[AppTeamMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
