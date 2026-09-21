from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from dicehub._core.membership import MembershipVisibility as MembershipVisibility


class ProjectVisibility(str, Enum):
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


class ProjectOrderField(str, Enum):
    PROJECT_ID = "project_id"
    NAME = "name"
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"


class SortOrder(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    project_id: str = Field(min_length=1, max_length=256)
    group_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(min_length=1)
    route: str = Field(min_length=1)
    visibility: ProjectVisibility


class ProjectDetail(Project):
    description: str | None
    avatar_url: str | None


class ProjectPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: tuple[Project, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class ProjectRole(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)


class ProjectMemberUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(min_length=1, max_length=256)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class ProjectMemberTeam(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(default=None, max_length=16_384)


class ProjectUserMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    user: ProjectMemberUser


class ProjectTeamMembership(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(min_length=1, max_length=256)
    member_id: str = Field(min_length=1, max_length=256)
    namespace_id: str = Field(min_length=1, max_length=256)
    role_id: str = Field(min_length=1, max_length=256)
    visibility: MembershipVisibility
    inherited: bool
    team: ProjectMemberTeam


class ProjectUserMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[ProjectUserMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)


class ProjectTeamMembershipPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    memberships: tuple[ProjectTeamMembership, ...]
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    cursor: str = Field(max_length=16_384)
