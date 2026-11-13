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
from dicehub._core.rest_mutations import mutation_outcome
from dicehub._core.rest_request import request
from dicehub._core.rest_v2 import RestV2Executor
from dicehub.errors import ProtocolError


def list(rest: RestV2Executor, variables: dict[str, object]) -> models.ConfigPage:
    wire = request(
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


def get(rest: RestV2Executor, variables: dict[str, object]) -> models.Config:
    wire = request(
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


@mutation_outcome
def create(rest: RestV2Executor, variables: dict[str, object]) -> models.Config:
    wire = request(
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


@mutation_outcome
def update(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/configs/{identifier(variables['configId'])}",
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
        path=f"api/v2/configs/{identifier(variables['configId'])}",
    )
    return None


def list_content(rest: RestV2Executor, variables: dict[str, object]) -> models.ConfigContentPage:
    wire = request(
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


def get_text(rest: RestV2Executor, variables: dict[str, object]) -> str:
    wire = request(
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


@mutation_outcome
def set_text(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PUT",
        path=f"api/v2/configs/{identifier(variables['configId'])}/text",
        body=request_body({"path": variables.get("path"), "content": variables.get("content")}),
    )
    return None


@mutation_outcome
def set_values(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="PATCH",
        path=f"api/v2/configs/{identifier(variables['configId'])}/values",
        body=request_body({"path": variables.get("path"), "updates": variables.get("updates")}),
    )
    return None


@mutation_outcome
def delete_content(rest: RestV2Executor, variables: dict[str, object]) -> None:
    request(
        rest,
        wire_models.Done,
        method="POST",
        path=f"api/v2/configs/{identifier(variables['configId'])}/content/delete",
        body=request_body({"area": variables.get("area"), "path": variables.get("path")}),
    )
    return None


@mutation_outcome
def import_geometry(
    rest: RestV2Executor, variables: dict[str, object]
) -> models.GeometryImportRuns:
    wire = request(
        rest,
        wire_models.GeometryRuns,
        method="POST",
        path=f"api/v2/configs/{identifier(variables['configId'])}/geometry/import",
        body=request_body({"filename": variables.get("filename")}),
    )
    return parse_model(models.GeometryImportRuns, wire.model_dump(mode="json"))
