from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from dicehub._core.async_graphql import AsyncGraphQLExecutor
from dicehub._core.status import raise_for_status
from dicehub.errors import (
    ConfigurationError,
    GraphQLError,
    HTTPError,
    MutationOutcomeUnknownError,
    ProtocolError,
    TransportError,
)
from dicehub.projects.models import SortOrder
from dicehub.resources._graphql import (
    CREATE_RESOURCE_TEXT_MUTATION,
    DELETE_RESOURCE_MUTATION,
    GET_RESOURCE_BY_KEY_QUERY,
    GET_RESOURCE_QUERY,
    GET_RESOURCE_TEXT_QUERY,
    LIST_RESOURCES_QUERY,
    SET_RESOURCE_TEXT_MUTATION,
    CreateResourceTextData,
    DeleteResourceData,
    GetResourceByKeyData,
    GetResourceData,
    GetResourceTextData,
    ListResourcesData,
    SetResourceTextData,
)
from dicehub.resources._validation import (
    data_key,
    validated_cursor,
    validated_data_path,
    validated_namespace_id,
    validated_offset,
    validated_page_size,
    validated_resource_id,
    validated_search_filter,
    validated_text,
    validated_text_response,
)
from dicehub.resources.models import Resource, ResourcePage, ResourceType
from dicehub.resources.service import _resource_from_payload, _validated_response

WireModelT = TypeVar("WireModelT", bound=BaseModel)
_AMBIGUOUS_MUTATION_ERRORS = (TransportError, HTTPError, GraphQLError, ProtocolError)
_MAX_TEXT_RESPONSE_BYTES = 13 * 1024 * 1024


class AsyncResourcesService:
    def __init__(self, graphql: AsyncGraphQLExecutor) -> None:
        self._graphql = graphql

    async def get(self, *, resource_id: str) -> Resource:
        result = await self._graphql.execute(
            operation_name="GetResource",
            query=GET_RESOURCE_QUERY,
            variables={"resourceId": validated_resource_id(resource_id)},
        )
        response = _validated_response(GetResourceData, result.data)
        payload = response.resources.get_resource
        raise_for_status(payload.status)
        if payload.resource is None:
            raise ProtocolError("dicehub returned a successful response without a resource.")
        return _resource_from_payload(payload.resource)

    async def get_by_key(self, *, namespace_id: str, path: str) -> Resource:
        result = await self._graphql.execute(
            operation_name="GetResourceByKey",
            query=GET_RESOURCE_BY_KEY_QUERY,
            variables={
                "namespaceId": validated_namespace_id(namespace_id),
                "key": data_key(path),
            },
        )
        response = _validated_response(GetResourceByKeyData, result.data)
        payload = response.resources.get_resource
        raise_for_status(payload.status)
        if payload.resource is None:
            raise ProtocolError("dicehub returned a successful response without a resource.")
        return _resource_from_payload(payload.resource)

    async def list(
        self,
        *,
        namespace_id: str,
        path: str = "",
        resource_type: ResourceType | None = None,
        search_filter: str | None = None,
        recursive: bool = False,
        order: SortOrder = SortOrder.ASC,
        offset: int = 0,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ResourcePage:
        if resource_type is not None and not isinstance(resource_type, ResourceType):
            raise ConfigurationError("Resource type is invalid.")
        if not isinstance(recursive, bool):
            raise ConfigurationError("Resource recursive flag is invalid.")
        if not isinstance(order, SortOrder):
            raise ConfigurationError("Resource sort order is invalid.")
        result = await self._graphql.execute(
            operation_name="ListResources",
            query=LIST_RESOURCES_QUERY,
            variables={
                "namespaceId": validated_namespace_id(namespace_id),
                "path": data_key(validated_data_path(path, allow_empty=True), allow_empty=True),
                "resourceType": resource_type.value if resource_type is not None else None,
                "searchFilter": validated_search_filter(search_filter),
                "deep": recursive,
                "order": order.value,
                "offset": float(validated_offset(offset)),
                "limit": float(validated_page_size(limit)),
                "cursor": validated_cursor(cursor),
            },
        )
        response = _validated_response(ListResourcesData, result.data)
        payload = response.resources.list_resources
        raise_for_status(payload.status)
        if payload.resources is None or payload.info is None:
            raise ProtocolError("dicehub returned a successful response without a resource page.")
        return ResourcePage(
            resources=tuple(_resource_from_payload(resource) for resource in payload.resources),
            offset=int(payload.info.offset),
            count=int(payload.info.count),
            cursor=payload.info.cursor,
        )

    async def get_text(self, *, resource_id: str) -> str:
        result = await self._graphql.execute(
            operation_name="GetResourceText",
            query=GET_RESOURCE_TEXT_QUERY,
            variables={"resourceId": validated_resource_id(resource_id)},
            max_response_bytes=_MAX_TEXT_RESPONSE_BYTES,
        )
        response = _validated_response(GetResourceTextData, result.data)
        payload = response.resources.get_text
        raise_for_status(payload.status)
        if payload.content is None:
            raise ProtocolError("dicehub returned a successful response without resource text.")
        return validated_text_response(payload.content)

    async def create_text(self, *, namespace_id: str, path: str, content: str) -> None:
        response = await self._execute_mutation(
            response_type=CreateResourceTextData,
            operation_name="CreateResourceText",
            query=CREATE_RESOURCE_TEXT_MUTATION,
            variables={
                "namespaceId": validated_namespace_id(namespace_id),
                "key": data_key(path),
                "content": validated_text(content),
            },
        )
        raise_for_status(response.resources.create_text.status)

    async def set_text(self, *, resource_id: str, content: str) -> None:
        response = await self._execute_mutation(
            response_type=SetResourceTextData,
            operation_name="SetResourceText",
            query=SET_RESOURCE_TEXT_MUTATION,
            variables={
                "resourceId": validated_resource_id(resource_id),
                "content": validated_text(content),
            },
        )
        raise_for_status(response.resources.set_text.status)

    async def delete(self, *, resource_id: str) -> None:
        response = await self._execute_mutation(
            response_type=DeleteResourceData,
            operation_name="DeleteResource",
            query=DELETE_RESOURCE_MUTATION,
            variables={"resourceId": validated_resource_id(resource_id)},
        )
        raise_for_status(response.resources.delete_resource.status)

    async def _execute_mutation(
        self,
        *,
        response_type: type[WireModelT],
        operation_name: str,
        query: str,
        variables: dict[str, object],
    ) -> WireModelT:
        mapped_error: MutationOutcomeUnknownError | None = None
        try:
            result = await self._graphql.execute(
                operation_name=operation_name,
                query=query,
                variables=variables,
            )
            return _validated_response(response_type, result.data)
        except _AMBIGUOUS_MUTATION_ERRORS as error:
            mapped_error = MutationOutcomeUnknownError(
                "The resource mutation may have completed, but dicehub did not confirm its "
                "outcome.",
                request_id=error.request_id,
            )
        assert mapped_error is not None
        raise mapped_error
