"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.projects._rest_models as wire_models
import dicehub.projects.models as models
from dicehub._core.rest_models import (
    convert,
    identifier,
    query_params,
    request_body,
    validate_page,
)
from dicehub._core.rest_mutations import mutation_outcome
from dicehub._core.rest_request import request
from dicehub._core.rest_v2 import RestV2Executor


@mutation_outcome
def create(rest: RestV2Executor, variables: dict[str, object]) -> models.ProjectDetail:
    wire = request(
        rest,
        wire_models.CreatedProject,
        method="POST",
        path="api/v2/projects",
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
        models.ProjectDetail,
        wire,
        (
            "project_id",
            "group_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "description",
            "avatar_url",
        ),
    )


@mutation_outcome
def update(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/projects/{identifier(variables['projectId'])}",
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


@mutation_outcome
def move(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/move",
        body=request_body({"to_group_id": variables.get("toGroupId")}),
    )
    return None


@mutation_outcome
def delete(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/projects/{identifier(variables['projectId'])}",
    )
    return None


def list_roles(
    rest: RestV2Executor, variables: dict[str, object]
) -> tuple[models.ProjectRole, ...]:
    wire = request(
        rest,
        wire_models.RoleList,
        method="GET",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/roles",
        params=query_params({}),
    )
    return tuple(convert(models.ProjectRole, item, ("role_id", "name")) for item in wire.items)


def list_user_members(
    rest: RestV2Executor, variables: dict[str, object]
) -> models.ProjectUserMembershipPage:
    wire = request(
        rest,
        wire_models.UserMembershipList,
        method="GET",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/members/users",
        params=query_params(
            {
                "include_inherited": variables.get("includeInherited"),
                "search": variables.get("searchFilter"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
                "deduplicate": variables.get("deduplicate"),
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
    return models.ProjectUserMembershipPage(
        memberships=tuple(
            convert(
                models.ProjectUserMembership,
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


def list_team_members(
    rest: RestV2Executor, variables: dict[str, object]
) -> models.ProjectTeamMembershipPage:
    wire = request(
        rest,
        wire_models.TeamMembershipList,
        method="GET",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/members/teams",
        params=query_params(
            {
                "include_inherited": variables.get("includeInherited"),
                "search": variables.get("searchFilter"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
                "deduplicate": variables.get("deduplicate"),
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
    return models.ProjectTeamMembershipPage(
        memberships=tuple(
            convert(
                models.ProjectTeamMembership,
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


@mutation_outcome
def add_member(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/members",
        body=request_body(
            {
                "member_id": variables.get("memberId"),
                "role_id": variables.get("roleId"),
                "visibility": variables.get("visibility"),
            }
        ),
    )
    return None


@mutation_outcome
def update_member(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/members/{identifier(variables['memberId'])}",
        body=request_body(
            {"role_id": variables.get("roleId"), "visibility": variables.get("visibility")}
        ),
    )
    return None


@mutation_outcome
def remove_member(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/projects/{identifier(variables['projectId'])}/members/{identifier(variables['memberId'])}",
    )
    return None
