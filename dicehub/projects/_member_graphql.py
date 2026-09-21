from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus
from dicehub.projects._graphql import DefaultMutationPayload, ListInfoPayload, _valid_positive_id

LIST_PROJECT_ROLES_QUERY = """
query ListProjectRoles($projectId: String!) {
  projects {
    listRolesByProjectId(projectId: $projectId) {
      status { succeeded error }
      roles { roleId name }
    }
  }
}
"""

LIST_PROJECT_USER_MEMBERSHIPS_QUERY = """
query ListProjectUserMemberships(
  $projectId: String!
  $includeInherited: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  projects {
    listUserMembershipsInProject(
      projectId: $projectId
      includeInherited: $includeInherited
      searchFilter: $searchFilter
      orderBy: "user_id"
      order: ASC
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      userMemberships {
        membershipId
        memberId
        namespaceId
        visibility
        roleId
        inherited
        user { userId firstName lastName username avatarUrl }
      }
    }
  }
}
"""

LIST_PROJECT_TEAM_MEMBERSHIPS_QUERY = """
query ListProjectTeamMemberships(
  $projectId: String!
  $includeInherited: Boolean!
  $deduplicate: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  projects {
    listTeamMembershipsInProject(
      projectId: $projectId
      includeInherited: $includeInherited
      deduplicate: $deduplicate
      searchFilter: $searchFilter
      orderBy: "team_id"
      order: ASC
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {
      status { succeeded error }
      info { offset count cursor }
      teamMemberships {
        membershipId
        memberId
        namespaceId
        visibility
        roleId
        inherited
        team { teamId name route avatarUrl }
      }
    }
  }
}
"""

ADD_PROJECT_MEMBER_MUTATION = """
mutation AddProjectMember(
  $projectId: String!
  $memberId: String!
  $roleId: String!
  $visibility: MembershipVisibilityEnum!
) {
  projects {
    addMemberToProject(
      projectId: $projectId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

UPDATE_PROJECT_MEMBER_MUTATION = """
mutation UpdateProjectMember(
  $projectId: String!
  $memberId: String!
  $roleId: String
  $visibility: MembershipVisibilityEnum
) {
  projects {
    updateProjectMembership(
      projectId: $projectId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

REMOVE_PROJECT_MEMBER_MUTATION = """
mutation RemoveProjectMember($projectId: String!, $memberId: String!) {
  projects {
    removeMemberFromProject(projectId: $projectId, memberId: $memberId) {
      status { succeeded error }
    }
  }
}
"""


class ProjectRolePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(alias="roleId", min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)

    @field_validator("role_id")
    @classmethod
    def validate_role_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid project role ID")
        return value


class ProjectMemberUserPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    user_id: str = Field(alias="userId", min_length=1, max_length=256)
    first_name: str | None = Field(alias="firstName", default=None, max_length=128)
    last_name: str | None = Field(alias="lastName", default=None, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    avatar_url: str | None = Field(alias="avatarUrl", default=None, max_length=16_384)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid project member user ID")
        return value


class ProjectMemberTeamPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(alias="avatarUrl", default=None, max_length=16_384)

    @field_validator("team_id")
    @classmethod
    def validate_team_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid project member team ID")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        if not value.startswith("/") or any(not character.isprintable() for character in value):
            raise ValueError("invalid project member team route")
        return value


class _MembershipPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    membership_id: str = Field(alias="membershipId", min_length=1, max_length=256)
    member_id: str = Field(alias="memberId", min_length=1, max_length=256)
    namespace_id: str = Field(alias="namespaceId", min_length=1, max_length=256)
    visibility: Literal["HIDDEN", "PRIVATE", "PUBLIC"]
    role_id: str = Field(alias="roleId", min_length=1, max_length=256)
    inherited: bool

    @field_validator("membership_id", "member_id", "namespace_id", "role_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid project membership ID")
        return value


class ProjectUserMembershipPayload(_MembershipPayload):
    user: ProjectMemberUserPayload


class ProjectTeamMembershipPayload(_MembershipPayload):
    team: ProjectMemberTeamPayload


class ListProjectRolesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    roles: list[ProjectRolePayload] | None


class ListProjectRoles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_roles: ListProjectRolesPayload = Field(alias="listRolesByProjectId")


class ListProjectRolesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: ListProjectRoles


class ListProjectUserMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[ProjectUserMembershipPayload] | None = Field(alias="userMemberships")


class ListProjectUserMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListProjectUserMembershipsPayload = Field(
        alias="listUserMembershipsInProject"
    )


class ListProjectUserMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: ListProjectUserMemberships


class ListProjectTeamMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[ProjectTeamMembershipPayload] | None = Field(alias="teamMemberships")


class ListProjectTeamMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListProjectTeamMembershipsPayload = Field(
        alias="listTeamMembershipsInProject"
    )


class ListProjectTeamMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: ListProjectTeamMemberships


class AddProjectMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    add_member: DefaultMutationPayload = Field(alias="addMemberToProject")


class AddProjectMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: AddProjectMember


class UpdateProjectMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_member: DefaultMutationPayload = Field(alias="updateProjectMembership")


class UpdateProjectMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: UpdateProjectMember


class RemoveProjectMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    remove_member: DefaultMutationPayload = Field(alias="removeMemberFromProject")


class RemoveProjectMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    projects: RemoveProjectMember
