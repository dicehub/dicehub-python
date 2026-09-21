from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus
from dicehub.apps._graphql import DefaultMutationPayload, ListInfoPayload, _valid_positive_id

LIST_APP_ROLES_QUERY = """
query ListAppRoles($appId: String!) {
  apps {
    listRolesByAppId(appId: $appId) {
      status { succeeded error }
      roles { roleId name }
    }
  }
}
"""

LIST_APP_USER_MEMBERSHIPS_QUERY = """
query ListAppUserMemberships(
  $appId: String!
  $includeInherited: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  apps {
    listUserMembershipsInApp(
      appId: $appId
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

LIST_APP_TEAM_MEMBERSHIPS_QUERY = """
query ListAppTeamMemberships(
  $appId: String!
  $includeInherited: Boolean!
  $deduplicate: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  apps {
    listTeamMembershipsInApp(
      appId: $appId
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

ADD_APP_MEMBER_MUTATION = """
mutation AddAppMember(
  $appId: String!
  $memberId: String!
  $roleId: String!
  $visibility: MembershipVisibilityEnum!
) {
  apps {
    addMemberToApp(
      appId: $appId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

UPDATE_APP_MEMBER_MUTATION = """
mutation UpdateAppMember(
  $appId: String!
  $memberId: String!
  $roleId: String
  $visibility: MembershipVisibilityEnum
) {
  apps {
    updateAppMembership(
      appId: $appId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

REMOVE_APP_MEMBER_MUTATION = """
mutation RemoveAppMember($appId: String!, $memberId: String!) {
  apps {
    removeMemberFromApp(appId: $appId, memberId: $memberId) {
      status { succeeded error }
    }
  }
}
"""


class AppRolePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(alias="roleId", min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)

    @field_validator("role_id")
    @classmethod
    def validate_role_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid app role ID")
        return value


class AppMemberUserPayload(BaseModel):
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
            raise ValueError("invalid app member user ID")
        return value


class AppMemberTeamPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(alias="avatarUrl", default=None, max_length=16_384)

    @field_validator("team_id")
    @classmethod
    def validate_team_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid app member team ID")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        if not value.startswith("/") or any(not character.isprintable() for character in value):
            raise ValueError("invalid app member team route")
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
            raise ValueError("invalid app membership ID")
        return value


class AppUserMembershipPayload(_MembershipPayload):
    user: AppMemberUserPayload


class AppTeamMembershipPayload(_MembershipPayload):
    team: AppMemberTeamPayload


class ListAppRolesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    roles: list[AppRolePayload] | None


class ListAppRoles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_roles: ListAppRolesPayload = Field(alias="listRolesByAppId")


class ListAppRolesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: ListAppRoles


class ListAppUserMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[AppUserMembershipPayload] | None = Field(alias="userMemberships")


class ListAppUserMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListAppUserMembershipsPayload = Field(alias="listUserMembershipsInApp")


class ListAppUserMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: ListAppUserMemberships


class ListAppTeamMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[AppTeamMembershipPayload] | None = Field(alias="teamMemberships")


class ListAppTeamMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListAppTeamMembershipsPayload = Field(alias="listTeamMembershipsInApp")


class ListAppTeamMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: ListAppTeamMemberships


class AddAppMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    add_member: DefaultMutationPayload = Field(alias="addMemberToApp")


class AddAppMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: AddAppMember


class UpdateAppMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_member: DefaultMutationPayload = Field(alias="updateAppMembership")


class UpdateAppMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: UpdateAppMember


class RemoveAppMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    remove_member: DefaultMutationPayload = Field(alias="removeMemberFromApp")


class RemoveAppMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    apps: RemoveAppMember
