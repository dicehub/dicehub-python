from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from dicehub._core.membership import MembershipVisibility as MembershipVisibility


class GroupVisibility(str, Enum):
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class GroupOrderField(str, Enum):
    GROUP_ID = "group_id"
    NAME = "name"
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    group_id: str = Field(min_length=1, max_length=256)
    parent_id: str | None = Field(default=None, min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(min_length=1, max_length=16_384)
    route: str = Field(min_length=1, max_length=16_384)
    visibility: GroupVisibility
    has_children: bool


class GroupDetail(Group):
    description: str | None
    avatar_url: str | None


class GroupPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: tuple[Group, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class GroupRole(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)


class GroupMemberUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(min_length=1, max_length=256)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class GroupMemberTeam(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class GroupUserMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    user: GroupMemberUser


class GroupTeamMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    team: GroupMemberTeam


class GroupUserMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[GroupUserMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class GroupTeamMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[GroupTeamMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
