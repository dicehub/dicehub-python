"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.resources._rest_models as wire_models
import dicehub.resources.models as models
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
from dicehub.errors import ProtocolError
from dicehub.resources._validation import validated_text_response


def list(rest: RestV2Executor, variables: dict[str, object]) -> models.ResourcePage:
    wire = request(
        rest,
        wire_models.ResourceList,
        method="GET",
        path="api/v2/resources",
        params=query_params(
            {
                "namespace_id": variables.get("namespaceId"),
                "path": variables.get("path"),
                "resource_type": variables.get("resourceType"),
                "search": variables.get("searchFilter"),
                "deep": variables.get("deep"),
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
    return models.ResourcePage(
        resources=tuple(
            convert(models.Resource, item, ("resource_id", "namespace_id", "key", "resource_type"))
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


def get(rest: RestV2Executor, variables: dict[str, object]) -> models.Resource:
    wire = request(
        rest,
        wire_models.ResourceDetail,
        method="GET",
        path=f"api/v2/resources/{identifier(variables['resourceId'], uuid=True)}",
        params=query_params({}),
    )
    return convert(models.Resource, wire, ("resource_id", "namespace_id", "key", "resource_type"))


def get_by_key(rest: RestV2Executor, variables: dict[str, object]) -> models.Resource:
    wire = request(
        rest,
        wire_models.ResourceDetail,
        method="GET",
        path="api/v2/resources/by-key",
        params=query_params(
            {"namespace_id": variables.get("namespaceId"), "key": variables.get("key")}
        ),
    )
    return convert(models.Resource, wire, ("resource_id", "namespace_id", "key", "resource_type"))


def get_text(rest: RestV2Executor, variables: dict[str, object]) -> str:
    wire = request(
        rest,
        wire_models.ResourceText,
        method="GET",
        path=f"api/v2/resources/{identifier(variables['resourceId'], uuid=True)}/text",
        params=query_params({}),
        max_response_bytes=13 * 1024 * 1024,
    )
    if wire.content is None:
        raise ProtocolError("dicehub returned no text content.")
    return validated_text_response(wire.content)


@mutation_outcome
def create_text(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="POST",
        path="api/v2/resources/texts",
        body=request_body(
            {
                "namespace_id": variables.get("namespaceId"),
                "key": variables.get("key"),
                "content": variables.get("content"),
            }
        ),
    )
    return None


@mutation_outcome
def set_text(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PUT",
        path=f"api/v2/resources/{identifier(variables['resourceId'], uuid=True)}/text",
        body=request_body({"content": variables.get("content")}),
    )
    return None


@mutation_outcome
def delete(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/resources/{identifier(variables['resourceId'], uuid=True)}",
    )
    return None
