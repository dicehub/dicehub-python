"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.apps._rest_models as wire_models
import dicehub.apps.models as models
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


def list(rest: RestV2Executor, variables: dict[str, object]) -> models.AppPage:
    wire = request(
        rest,
        wire_models.AppList,
        method="GET",
        path="api/v2/apps",
        params=query_params(
            {
                "view": "summary",
                "project_id": variables.get("projectId"),
                "search": variables.get("searchFilter"),
                "order_by": variables.get("orderBy"),
                "order": variables.get("order"),
                "offset": variables.get("offset"),
                "limit": variables.get("limit"),
                "cursor": variables.get("cursor"),
                "is_published": (
                    "all" if variables.get("isPublished") is None else variables["isPublished"]
                ),
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
    return models.AppPage(
        apps=tuple(
            convert(
                models.App,
                item,
                (
                    "app_id",
                    "project_id",
                    "name",
                    "display_route",
                    "route",
                    "visibility",
                    "app_type",
                ),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


def get(rest: RestV2Executor, variables: dict[str, object]) -> models.AppDetail:
    wire = request(
        rest,
        wire_models.AppDetail,
        method="GET",
        path=f"api/v2/apps/{identifier(variables['appId'])}",
        params=query_params({}),
    )
    return convert(
        models.AppDetail,
        wire,
        (
            "app_id",
            "project_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "app_type",
            "description",
            "template_id",
            "template_name",
            "template_version",
            "template_slug",
            "icon_path",
            "preview_url",
        ),
    )


def get_by_route(rest: RestV2Executor, variables: dict[str, object]) -> models.AppDetail:
    wire = request(
        rest,
        wire_models.AppDetail,
        method="GET",
        path="api/v2/apps/by-route",
        params=query_params({"route": variables.get("route")}),
    )
    return convert(
        models.AppDetail,
        wire,
        (
            "app_id",
            "project_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "app_type",
            "description",
            "template_id",
            "template_name",
            "template_version",
            "template_slug",
            "icon_path",
            "preview_url",
        ),
    )


@mutation_outcome
def create(rest: RestV2Executor, variables: dict[str, object]) -> models.AppDetail:
    wire = request(
        rest,
        wire_models.AppDetail,
        method="POST",
        path="api/v2/apps",
        body=request_body(
            {
                "project_id": variables.get("projectId"),
                "template_id": variables.get("templateId"),
                "name": variables.get("name"),
                "description": variables.get("description"),
            }
        ),
    )
    return convert(
        models.AppDetail,
        wire,
        (
            "app_id",
            "project_id",
            "name",
            "display_route",
            "route",
            "visibility",
            "app_type",
            "description",
            "template_id",
            "template_name",
            "template_version",
            "template_slug",
            "icon_path",
            "preview_url",
        ),
    )


@mutation_outcome
def update(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/apps/{identifier(variables['appId'])}",
        body=request_body(
            {"name": variables.get("name"), "description": variables.get("description")}
        ),
    )
    return None


@mutation_outcome
def delete(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/apps/{identifier(variables['appId'])}",
    )
    return None


def list_roles(rest: RestV2Executor, variables: dict[str, object]) -> tuple[models.AppRole, ...]:
    wire = request(
        rest,
        wire_models.RoleList,
        method="GET",
        path=f"api/v2/apps/{identifier(variables['appId'])}/roles",
        params=query_params({}),
    )
    return tuple(convert(models.AppRole, item, ("role_id", "name")) for item in wire.items)


def list_user_members(
    rest: RestV2Executor, variables: dict[str, object]
) -> models.AppUserMembershipPage:
    wire = request(
        rest,
        wire_models.UserMembershipList,
        method="GET",
        path=f"api/v2/apps/{identifier(variables['appId'])}/members/users",
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
    return models.AppUserMembershipPage(
        memberships=tuple(
            convert(
                models.AppUserMembership,
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
) -> models.AppTeamMembershipPage:
    wire = request(
        rest,
        wire_models.TeamMembershipList,
        method="GET",
        path=f"api/v2/apps/{identifier(variables['appId'])}/members/teams",
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
    return models.AppTeamMembershipPage(
        memberships=tuple(
            convert(
                models.AppTeamMembership,
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
        path=f"api/v2/apps/{identifier(variables['appId'])}/members",
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
        path=f"api/v2/apps/{identifier(variables['appId'])}/members/{identifier(variables['memberId'])}",
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
        path=f"api/v2/apps/{identifier(variables['appId'])}/members/{identifier(variables['memberId'])}",
    )
    return None
