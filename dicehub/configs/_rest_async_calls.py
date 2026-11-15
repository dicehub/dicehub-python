"""Fixed REST calls and mappings for this domain."""

from __future__ import annotations

import dicehub.configs._rest_models as wire_models
import dicehub.configs.models as models
from dicehub._core.rest_models import (
    convert,
    identifier,
    parse_model,
    query_params,
    request_body,
    validate_page,
)
from dicehub._core.rest_mutations import async_mutation_outcome
from dicehub._core.rest_request import async_request as request
from dicehub._core.rest_v2 import AsyncRestV2Executor
from dicehub.errors import ProtocolError


async def list(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.ConfigPage:
    wire = await request(
        rest,
        wire_models.ConfigList,
        method="GET",
        path="api/v2/configs",
        params=query_params(
            {
                "app_id": variables.get("appId"),
                "search": variables.get("searchFilter"),
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
    return models.ConfigPage(
        configs=tuple(
            convert(
                models.Config,
                item,
                (
                    "config_id",
                    "app_id",
                    "config_internal_id",
                    "name",
                    "description",
                    "is_default",
                    "template_version",
                    "updating",
                ),
            )
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


async def get(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.Config:
    wire = await request(
        rest,
        wire_models.ConfigDetail,
        method="GET",
        path=f"api/v2/configs/{identifier(variables['configId'])}",
        params=query_params({}),
    )
    return convert(
        models.Config,
        wire,
        (
            "config_id",
            "app_id",
            "config_internal_id",
            "name",
            "description",
            "is_default",
            "template_version",
            "updating",
        ),
    )


@async_mutation_outcome
async def create(rest: AsyncRestV2Executor, variables: dict[str, object]) -> models.Config:
    wire = await request(
        rest,
        wire_models.ConfigDetail,
        method="POST",
        path="api/v2/configs",
        body=request_body(
            {
                "app_id": variables.get("appId"),
                "config_id": variables.get("sourceConfigId"),
                "name": variables.get("name"),
                "description": variables.get("description"),
            }
        ),
    )
    return convert(
        models.Config,
        wire,
        (
            "config_id",
            "app_id",
            "config_internal_id",
            "name",
            "description",
            "is_default",
            "template_version",
            "updating",
        ),
    )


@async_mutation_outcome
async def update(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/configs/{identifier(variables['configId'])}",
        body=request_body(
            {"name": variables.get("name"), "description": variables.get("description")}
        ),
    )
    return None


@async_mutation_outcome
async def delete(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="DELETE",
        path=f"api/v2/configs/{identifier(variables['configId'])}",
    )
    return None


async def list_content(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> models.ConfigContentPage:
    wire = await request(
        rest,
        wire_models.ConfigContentList,
        method="GET",
        path=f"api/v2/configs/{identifier(variables['configId'])}/content",
        params=query_params(
            {
                "area": variables.get("area"),
                "path": variables.get("path"),
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
    return models.ConfigContentPage(
        entries=tuple(
            convert(models.ConfigContentEntry, item, ("path", "resource_type"))
            for item in wire.items
        ),
        offset=wire.offset,
        count=wire.count,
        cursor=wire.cursor,
    )


async def get_text(rest: AsyncRestV2Executor, variables: dict[str, object]) -> str:
    wire = await request(
        rest,
        wire_models.ConfigTextResponse,
        method="GET",
        path=f"api/v2/configs/{identifier(variables['configId'])}/text",
        params=query_params({"path": variables.get("path")}),
        max_response_bytes=13 * 1024 * 1024,
    )
    if wire.content is None:
        raise ProtocolError("dicehub returned no text content.")
    return wire.content


@async_mutation_outcome
async def set_text(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PUT",
        path=f"api/v2/configs/{identifier(variables['configId'])}/text",
        body=request_body({"path": variables.get("path"), "content": variables.get("content")}),
    )
    return None


@async_mutation_outcome
async def set_values(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/configs/{identifier(variables['configId'])}/values",
        body=request_body({"path": variables.get("path"), "updates": variables.get("updates")}),
    )
    return None


@async_mutation_outcome
async def delete_content(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    await request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/configs/{identifier(variables['configId'])}/content/delete",
        body=request_body({"area": variables.get("area"), "path": variables.get("path")}),
    )
    return None


@async_mutation_outcome
async def import_geometry(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> models.GeometryImportRuns:
    wire = await request(
        rest,
        wire_models.GeometryRuns,
        method="POST",
        path=f"api/v2/configs/{identifier(variables['configId'])}/geometry/import",
        body=request_body({"filename": variables.get("filename")}),
    )
    return parse_model(models.GeometryImportRuns, wire.model_dump(mode="json"))
