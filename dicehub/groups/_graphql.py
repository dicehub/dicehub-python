from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dicehub._core.status import ResponseStatus

_GROUP_SUMMARY_FIELDS = """
        groupId
        parentId
        name
        displayRoute
        route
        visibility
        hasChildren
"""

_GROUP_DETAIL_FIELDS = f"""
{_GROUP_SUMMARY_FIELDS}
        description
        avatarUrl
"""

LIST_GROUPS_QUERY = f"""
query ListGroups(
  $userId: String
  $parentId: String
  $searchFilter: String
  $orderBy: String!
  $order: OrderTypeEnum!
  $offset: Float!
  $limit: Float!
  $cursor: String
) {{
  groups {{
    listGroups(
      userId: $userId
      parentId: $parentId
      searchFilter: $searchFilter
      orderBy: $orderBy
      order: $order
      offset: $offset
      limit: $limit
      ahead: 1
      cursor: $cursor
    ) {{
      status {{ succeeded error }}
      info {{ offset count cursor }}
      groups {{
{_GROUP_SUMMARY_FIELDS}
      }}
    }}
  }}
}}
"""

GET_GROUP_QUERY = f"""
query GetGroup($groupId: String!) {{
  groups {{
    getGroupById(groupId: $groupId) {{
      status {{ succeeded error }}
      group {{
{_GROUP_DETAIL_FIELDS}
      }}
    }}
  }}
}}
"""

GET_GROUP_BY_ROUTE_QUERY = f"""
query GetGroupByRoute($route: String!) {{
  groups {{
    getGroupByRoute(route: $route) {{
      # The server derives SQL fields from the first nested selection for this resolver.
      # Keep group before status until getGroupByRoute excludes status server-side.
      group {{
{_GROUP_DETAIL_FIELDS}
      }}
      status {{ succeeded error }}
    }}
  }}
}}
"""

UPDATE_GROUP_MUTATION = """
mutation UpdateGroup(
  $groupId: String!
  $name: String
  $slug: String
  $description: String
  $visibility: GroupVisibilityEnum
) {
  groups {
    updateGroup(
      groupId: $groupId
      name: $name
      slug: $slug
      description: $description
      visibility: $visibility
    ) {
      status { succeeded error }
    }
  }
}
"""

CREATE_GROUP_MUTATION = f"""
mutation CreateGroup(
  $name: String!
  $slug: String!
  $description: String
  $groupId: String
  $visibility: GroupVisibilityEnum!
) {{
  groups {{
    createGroup(
      name: $name
      slug: $slug
      description: $description
      groupId: $groupId
      visibility: $visibility
    ) {{
      status {{ succeeded error }}
      group {{
{_GROUP_DETAIL_FIELDS}
      }}
    }}
  }}
}}
"""

DELETE_GROUP_MUTATION = """
mutation DeleteGroup($groupId: String!) {
  groups {
    deleteGroup(groupId: $groupId) {
      status { succeeded error }
    }
  }
}
"""

MOVE_GROUP_MUTATION = """
mutation MoveGroup($groupId: String!, $toGroupId: String!) {
  groups {
    moveGroup(groupId: $groupId, toGroupId: $toGroupId) {
      status { succeeded error }
    }
  }
}
"""

UPDATE_GROUP_AVATAR_MUTATION = """
mutation UpdateGroupAvatar($groupId: String!, $avatar: Upload!) {
  groups {
    updateGroup(groupId: $groupId, avatar: $avatar) {
      status { succeeded error }
    }
  }
}
"""


def _valid_positive_id(value: str) -> bool:
    return (
        0 < len(value) <= 256 and value.isascii() and value.isdigit() and not value.startswith("0")
    )


def _valid_printable(value: str, *, max_length: int) -> bool:
    return 0 < len(value) <= max_length and all(character.isprintable() for character in value)


class GroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    group_id: str = Field(alias="groupId", min_length=1, max_length=256)
    parent_id: str | None = Field(alias="parentId", min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    display_route: str = Field(alias="displayRoute", min_length=1, max_length=16_384)
    route: str = Field(min_length=1, max_length=16_384)
    visibility: Literal["INTERNAL", "PRIVATE", "PUBLIC"]
    has_children: bool | None = Field(alias="hasChildren")

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        if not _valid_positive_id(value):
            raise ValueError("invalid group ID")
        return value

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, value: str | None) -> str | None:
        if value is not None and not _valid_positive_id(value):
            raise ValueError("invalid parent group ID")
        return value

    @field_validator("name", "display_route")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not _valid_printable(value, max_length=16_384):
            raise ValueError("invalid group text")
        return value

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        if not value.startswith("/") or any(not character.isprintable() for character in value):
            raise ValueError("invalid group route")
        return value


class GroupDetailPayload(GroupPayload):
    description: str | None
    avatar_url: str | None = Field(alias="avatarUrl", max_length=16_384)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and "\0" in value:
            raise ValueError("invalid group description")
        return value

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is not None and any(not character.isprintable() for character in value):
            raise ValueError("invalid group avatar URL")
        return value


class ListInfoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    offset: float = Field(ge=0)
    count: float = Field(ge=0)
    cursor: str = Field(max_length=16_384)

    @field_validator("offset", "count")
    @classmethod
    def validate_integer_float(cls, value: float) -> float:
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("invalid group page information")
        return value


class ListGroupsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    info: ListInfoPayload | None
    groups: list[GroupPayload] | None


class ListGroups(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    list_groups: ListGroupsPayload = Field(alias="listGroups")


class ListGroupsData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: ListGroups


class SingleGroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    group: GroupDetailPayload | None


class GetGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_group: SingleGroupPayload = Field(alias="getGroupById")


class GetGroupData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: GetGroup


class GetGroupByRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    get_group: SingleGroupPayload = Field(alias="getGroupByRoute")


class GetGroupByRouteData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: GetGroupByRoute


class DefaultMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus


class UpdateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_group: DefaultMutationPayload = Field(alias="updateGroup")


class UpdateGroupData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: UpdateGroup


class CreatedGroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ResponseStatus
    group: GroupDetailPayload | None


class CreateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    create_group: CreatedGroupPayload = Field(alias="createGroup")


class CreateGroupData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: CreateGroup


class DeleteGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    delete_group: DefaultMutationPayload = Field(alias="deleteGroup")


class DeleteGroupData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: DeleteGroup


class MoveGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    move_group: DefaultMutationPayload = Field(alias="moveGroup")


class MoveGroupData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: MoveGroup


class UpdateGroupAvatar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    update_group: DefaultMutationPayload = Field(alias="updateGroup")


class UpdateGroupAvatarData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    groups: UpdateGroupAvatar
