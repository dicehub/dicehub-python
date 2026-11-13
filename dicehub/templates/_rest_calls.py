"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.templates._rest_models as wire_models
import dicehub.templates.models as models
from dicehub._core.rest_models import (
    identifier,
    parse_model,
    query_params,
    validate_page,
)
from dicehub._core.rest_request import request
from dicehub._core.rest_v2 import RestV2Executor


def list(rest: RestV2Executor, variables: dict[str, object]) -> models.TemplatePage:
    wire = request(
        rest,
        wire_models.TemplateList,
        method="GET",
        path="api/v2/templates",
        params=query_params(
            {
                "search": variables.get("searchFilter"),
                "template_type": variables.get("templateType"),
                "tags": variables.get("tags"),
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
    return models.TemplatePage(
        templates=tuple(template(item) for item in wire.items),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


def get(rest: RestV2Executor, variables: dict[str, object]) -> models.Template:
    wire = request(
        rest,
        wire_models.TemplateDetail,
        method="GET",
        path=f"api/v2/templates/{identifier(variables['templateId'])}",
        params=query_params({}),
    )
    return template(wire)


def get_by_route(rest: RestV2Executor, variables: dict[str, object]) -> models.Template:
    wire = request(
        rest,
        wire_models.TemplateDetail,
        method="GET",
        path="api/v2/templates/by-route",
        params=query_params({"route": variables.get("route")}),
    )
    return template(wire)


def template(wire: wire_models.TemplateDetail) -> models.Template:
    data = wire.model_dump(mode="json", exclude={"template_type", "tags"})
    data["tags"] = [{"tag_id": tag.tag_id, "tag": tag.tag} for tag in wire.tags]
    return parse_model(models.Template, data)
