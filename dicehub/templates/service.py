from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from dicehub._core.graphql import GraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import ProtocolError
from dicehub.projects.models import SortOrder
from dicehub.templates._graphql import (
    GET_TEMPLATE_BY_ROUTE_QUERY,
    GET_TEMPLATE_QUERY,
    LIST_TEMPLATES_QUERY,
    GetTemplateByRouteData,
    GetTemplateData,
    ListTemplatesData,
    SingleTemplatePayload,
    TemplatePayload,
)
from dicehub.templates._validation import (
    validated_cursor,
    validated_enum,
    validated_id,
    validated_offset,
    validated_optional_enum,
    validated_page_size,
    validated_route,
    validated_search_filter,
    validated_tags,
)
from dicehub.templates.models import (
    Template,
    TemplateOrderField,
    TemplatePage,
    TemplateTag,
    TemplateType,
)

WireModelT = TypeVar("WireModelT", bound=BaseModel)


class TemplatesService:
    def __init__(self, graphql: GraphQLExecutor) -> None:
        self._graphql = graphql

    def list(
        self,
        *,
        search_filter: str | None = None,
        template_type: TemplateType | None = TemplateType.APP_TEMPLATE,
        tags: Sequence[str] | None = None,
        order_by: TemplateOrderField = TemplateOrderField.NAME,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> TemplatePage:
        valid_template_type = validated_optional_enum(
            template_type,
            TemplateType,
            "template type",
        )
        valid_order_by = validated_enum(order_by, TemplateOrderField, "template order field")
        valid_order = validated_enum(order, SortOrder, "template sort order")
        result = self._graphql.execute(
            operation_name="ListTemplates",
            query=LIST_TEMPLATES_QUERY,
            variables={
                "searchFilter": validated_search_filter(search_filter),
                "templateType": (
                    valid_template_type.value if valid_template_type is not None else None
                ),
                "tags": validated_tags(tags),
                "orderBy": valid_order_by.value,
                "order": valid_order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(ListTemplatesData, result.data)
        payload = response.templates.list_templates
        raise_for_status(payload.status)
        if payload.templates is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a template page.")
        return TemplatePage(
            templates=tuple(_template_from_payload(template) for template in payload.templates),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    def get(self, *, template_id: str) -> Template:
        result = self._graphql.execute(
            operation_name="GetTemplate",
            query=GET_TEMPLATE_QUERY,
            variables={"templateId": validated_id(template_id)},
        )
        response = _validated_response(GetTemplateData, result.data)
        return _template_from_single(response.templates.get_template)

    def get_by_route(self, *, route: str) -> Template:
        result = self._graphql.execute(
            operation_name="GetTemplateByRoute",
            query=GET_TEMPLATE_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(GetTemplateByRouteData, result.data)
        return _template_from_single(response.templates.get_template)


def _validated_response(
    response_type: type[WireModelT],
    data: dict[str, object],
) -> WireModelT:
    response: WireModelT | None = None
    try:
        response = response_type.model_validate(data)
    except ValidationError:
        pass
    if response is None:
        raise ProtocolError("dicehub returned an incompatible template response.")
    return response


def _template_from_payload(payload: TemplatePayload) -> Template:
    tags = sorted(payload.tags, key=lambda tag: int(tag.tag_id))
    return Template(
        template_id=payload.template_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        client_type=payload.client_type,
        route=payload.route,
        image_path=payload.image_path,
        icon_path=payload.icon_path,
        tags=tuple(TemplateTag(tag_id=tag.tag_id, tag=tag.tag) for tag in tags),
        created_at=payload.created_at,
        updated_at=payload.updated_at,
    )


def _template_from_single(payload: SingleTemplatePayload) -> Template:
    raise_for_status(payload.status)
    if payload.template is None:
        raise ProtocolError("dicehub returned a successful response without a template.")
    return _template_from_payload(payload.template)
