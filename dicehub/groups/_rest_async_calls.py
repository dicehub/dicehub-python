"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.groups._rest_models as wire_models
import dicehub.groups.models as models
from dicehub._core.rest_models import (
    convert,
    identifier,
    query_params,
    request_body,
    validate_page,
)
from dicehub._core.rest_mutations import async_mutation_outcome
from dicehub._core.rest_request import async_request as request
from dicehub._core.rest_v2 import AsyncRestV2Executor


async def list(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.GroupPage:
    wire = await request(
        rest,
        wire_models.GroupList,
        method="GET",
        path="api/v2/groups",
        params=query_params(
            {
                "view": "summary",
                "user_id": variables.get("userId"),
                "parent_id": variables.get("parentId"),
                "search": variables.get("searchFilter"),
                "order_by": variables.get("orderBy"),
                "order": variables.get("order"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
            }
        ),
    )
    validate_page(
        size=len(wire.items),
        limit=wire.limit,
        offset=wire.offset,
        count=wire.count,
        has_more=wire.has_more,
        requested_limit=variables.get("limit"),
        requested_offset=variables.get("offset"),
    )
    return models.GroupPage(
        groups=tuple(
            convert(
                models.Group,
                item,
                (
                    "group_id",
                    "parent_id",
                    "name",
                    "display_route",
                    "route",
                    "visibility",
                    "has_children",
                ),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


async def get(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.GroupDetail:
    wire = await request(
        rest,
        wire_models.GroupDetail,
        method="GET",
        path=f"api/v2/groups/{identifier(variables['groupId'])}",
        params=query_params({}),
    )
    return convert(
        models.GroupDetail,
        wire,
        (
            "group_id",
            "parent_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "has_children",
            "description",
            "avatar_url",
        ),
    )


async def get_by_route(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> models.GroupDetail:
    wire = await request(
        rest,
        wire_models.GroupDetail,
        method="GET",
        path="api/v2/groups/by-route",
        params=query_params({"route": variables.get("route")}),
    )
    return convert(
        models.GroupDetail,
        wire,
        (
            "group_id",
            "parent_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "has_children",
            "description",
            "avatar_url",
        ),
    )


@async_mutation_outcome
async def create(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.GroupDetail:
    wire = await request(
        rest,
        wire_models.GroupDetail,
        method="POST",
        path="api/v2/groups",
        body=request_body(
            {
                "name": variables.get("name"),
                "slug": variables.get("slug"),
                "description": variables.get("description"),
                "group_id": variables.get("groupId"),
                "visibility": variables.get("visibility"),
            }
        ),
    )
    return convert(
        models.GroupDetail,
        wire,
        (
            "group_id",
            "parent_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "has_children",
            "description",
            "avatar_url",
        ),
    )


@async_mutation_outcome
async def update(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/groups/{identifier(variables['groupId'])}",
        body=request_body(
            {
                "name": variables.get("name"),
                "slug": variables.get("slug"),
                "description": variables.get("description"),
                "visibility": variables.get("visibility"),
            }
        ),
    )
    return None


@async_mutation_outcome
async def delete(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/groups/{identifier(variables['groupId'])}",
    )
    return None


@async_mutation_outcome
async def move(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/move",
        body=request_body({"to_group_id": variables.get("toGroupId")}),
    )
    return None


@async_mutation_outcome
async def set_avatar(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/groups/{identifier(variables['groupId'])}",
        body=request_body({"avatar": variables.get("avatar")}),
    )
    return None


@async_mutation_outcome
async def clear_avatar(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/groups/{identifier(variables['groupId'])}",
        body=request_body({"avatar": variables.get("avatar")}),
    )
    return None


async def list_roles(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> tuple[models.GroupRole, ...]:
    wire = await request(
        rest,
        wire_models.RoleList,
        method="GET",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/roles",
        params=query_params({}),
    )
    return tuple(convert(models.GroupRole, item, ("role_id", "name")) for item in wire.items)


async def list_user_members(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> models.GroupUserMembershipPage:
    wire = await request(
        rest,
        wire_models.UserMembershipList,
        method="GET",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/members/users",
        params=query_params(
            {
                "include_inherited": variables.get("includeInherited"),
                "deduplicate": variables.get("deduplicate"),
                "search": variables.get("searchFilter"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
            }
        ),
    )
    validate_page(
        size=len(wire.items),
        limit=wire.limit,
        offset=wire.offset,
        count=wire.count,
        has_more=wire.has_more,
        requested_limit=variables.get("limit"),
        requested_offset=variables.get("offset"),
    )
    return models.GroupUserMembershipPage(
        memberships=tuple(
            convert(
                models.GroupUserMembership,
                item,
                (
                    "membership_id",
                    "member_id",
                    "namespace_id",
                    "role_id",
                    "visibility",
                    "inherited",
                    "user",
                ),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


async def list_team_members(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> models.GroupTeamMembershipPage:
    wire = await request(
        rest,
        wire_models.TeamMembershipList,
        method="GET",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/members/teams",
        params=query_params(
            {
                "include_inherited": variables.get("includeInherited"),
                "deduplicate": variables.get("deduplicate"),
                "search": variables.get("searchFilter"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
            }
        ),
    )
    validate_page(
        size=len(wire.items),
        limit=wire.limit,
        offset=wire.offset,
        count=wire.count,
        has_more=wire.has_more,
        requested_limit=variables.get("limit"),
        requested_offset=variables.get("offset"),
    )
    return models.GroupTeamMembershipPage(
        memberships=tuple(
            convert(
                models.GroupTeamMembership,
                item,
                (
                    "membership_id",
                    "member_id",
                    "namespace_id",
                    "role_id",
                    "visibility",
                    "inherited",
                    "team",
                ),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


@async_mutation_outcome
async def add_member(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/members",
        body=request_body(
            {
                "member_id": variables.get("memberId"),
                "role_id": variables.get("roleId"),
                "visibility": variables.get("visibility"),
            }
        ),
    )
    return None


@async_mutation_outcome
async def update_member(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/members/{identifier(variables['memberId'])}",
        body=request_body(
            {"role_id": variables.get("roleId"), "visibility": variables.get("visibility")}
        ),
    )
    return None


@async_mutation_outcome
async def remove_member(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/groups/{identifier(variables['groupId'])}/members/{identifier(variables['memberId'])}",
    )
    return None
