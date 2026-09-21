from __future__ import annotations

from collections.abc import Sequence

from dicehub._core.async_graphql import AsyncGraphQLExecutor
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
    TemplateType,
)
from dicehub.templates.service import (
    _template_from_payload,
    _template_from_single,
    _validated_response,
)


class AsyncTemplatesService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def list(
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
        result = await self._graphql.execute(
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

    async def get(self, *, template_id: str) -> Template:
        result = await self._graphql.execute(
            operation_name="GetTemplate",
            query=GET_TEMPLATE_QUERY,
            variables={"templateId": validated_id(template_id)},
        )
        response = _validated_response(GetTemplateData, result.data)
        return _template_from_single(response.templates.get_template)

    async def get_by_route(self, *, route: str) -> Template:
        result = await self._graphql.execute(
            operation_name="GetTemplateByRoute",
            query=GET_TEMPLATE_BY_ROUTE_QUERY,
            variables={"route": validated_route(route)},
        )
        response = _validated_response(GetTemplateByRouteData, result.data)
        return _template_from_single(response.templates.get_template)
