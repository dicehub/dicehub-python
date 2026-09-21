from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus
from dicehub.groups._graphql import DefaultMutationPayload, ListInfoPayload, _valid_positive_id

LIST_GROUP_ROLES_QUERY = """
query ListGroupRoles($groupId: String!) {
  groups {
    listRolesByGroupId(groupId: $groupId) {
      status { succeeded error }
      roles { roleId name }
    }
  }
}
"""

LIST_GROUP_USER_MEMBERSHIPS_QUERY = """
query ListGroupUserMemberships(
  $groupId: String!
  $includeInherited: Boolean!
  $deduplicate: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  groups {
    listUserMembershipsInGroup(
      groupId: $groupId
      includeInherited: $includeInherited
      deduplicate: $deduplicate
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

LIST_GROUP_TEAM_MEMBERSHIPS_QUERY = """
query ListGroupTeamMemberships(
  $groupId: String!
  $includeInherited: Boolean!
  $deduplicate: Boolean!
  $searchFilter: String
  $offset: Float!
  $limit: Float!
  $cursor: String
) {
  groups {
    listTeamMembershipsInGroup(
      groupId: $groupId
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

ADD_GROUP_MEMBER_MUTATION = """
mutation AddGroupMember(
  $groupId: String!
  $memberId: String!
  $roleId: String!
  $visibility: MembershipVisibilityEnum!
) {
  groups {
    addMemberToGroup(
      groupId: $groupId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

UPDATE_GROUP_MEMBER_MUTATION = """
mutation UpdateGroupMember(
  $groupId: String!
  $memberId: String!
  $roleId: String
  $visibility: MembershipVisibilityEnum
) {
  groups {
    updateGroupMembership(
      groupId: $groupId
      memberId: $memberId
      roleId: $roleId
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

REMOVE_GROUP_MEMBER_MUTATION = """
mutation RemoveGroupMember($groupId: String!, $memberId: String!) {
  groups {
    removeMemberFromGroup(groupId: $groupId, memberId: $memberId) {
      status { succeeded error }
    }
  }
}
"""


class GroupRolePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role_id: str = Field(alias="roleId", min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=128)

    @field_validator("role_id")
    @classmethod
    def validate_role_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid group role ID")
        return value


class GroupMemberUserPayload(BaseModel):
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
            raise ValueError("invalid group member user ID")
        return value


class GroupMemberTeamPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    route: str = Field(min_length=1, max_length=16_384)
    avatar_url: str | None = Field(alias="avatarUrl", default=None, max_length=16_384)

    @field_validator("team_id")
    @classmethod
    def validate_team_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid group member team ID")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        if not value.startswith("/") or any(not character.isprintable() for character in value):
            raise ValueError("invalid group member team route")
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
            raise ValueError("invalid group membership ID")
        return value


class GroupUserMembershipPayload(_MembershipPayload):
    user: GroupMemberUserPayload


class GroupTeamMembershipPayload(_MembershipPayload):
    team: GroupMemberTeamPayload


class ListGroupRolesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    roles: list[GroupRolePayload] | None


class ListGroupRoles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_roles: ListGroupRolesPayload = Field(alias="listRolesByGroupId")


class ListGroupRolesData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: ListGroupRoles


class ListGroupUserMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[GroupUserMembershipPayload] | None = Field(alias="userMemberships")


class ListGroupUserMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListGroupUserMembershipsPayload = Field(alias="listUserMembershipsInGroup")


class ListGroupUserMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: ListGroupUserMemberships


class ListGroupTeamMembershipsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    memberships: list[GroupTeamMembershipPayload] | None = Field(alias="teamMemberships")


class ListGroupTeamMemberships(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_memberships: ListGroupTeamMembershipsPayload = Field(alias="listTeamMembershipsInGroup")


class ListGroupTeamMembershipsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: ListGroupTeamMemberships


class AddGroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    add_member: DefaultMutationPayload = Field(alias="addMemberToGroup")


class AddGroupMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: AddGroupMember


class UpdateGroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_member: DefaultMutationPayload = Field(alias="updateGroupMembership")


class UpdateGroupMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: UpdateGroupMember


class RemoveGroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    remove_member: DefaultMutationPayload = Field(alias="removeMemberFromGroup")


class RemoveGroupMemberData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: RemoveGroupMember
