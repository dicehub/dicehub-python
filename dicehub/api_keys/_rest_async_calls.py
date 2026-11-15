"""Fixed routes for managed API-key administration."""

from __future__ import annotations

import builtins

import dicehub.api_keys._rest_models as wire_models
from dicehub._core.rest_models import (
    identifier,
    parse_model,
    query_params,
    request_body,
)
from dicehub._core.rest_mutations import async_mutation_outcome
from dicehub._core.rest_request import async_request as request
from dicehub._core.rest_v2 import AsyncRestV2Executor
from dicehub.api_keys.models import ApiKey, CreatedApiKey, NamespacePermission
from dicehub.errors import APIError, ProtocolError


@async_mutation_outcome
async def create(rest: AsyncRestV2Executor, variables: dict[str, object]) -> CreatedApiKey:
    path = f"api/v2/namespaces/{identifier(variables['namespaceId'])}/api-keys"
    body = request_body(
        {
            "name": variables["name"],
            "permissions": variables["permissions"],
            "not_before": variables["notBefore"],
            "expires_at": variables["expiresAt"],
        }
    )
    wire = await request(rest, wire_models.CreatedApiKeyDetail, method="POST", path=path, body=body)
    metadata = parse_model(ApiKey, wire.model_dump(mode="json", exclude={"value"}))
    return CreatedApiKey(**metadata.model_dump(), value=wire.value)


async def get(rest: AsyncRestV2Executor, variables: dict[str, object]) -> ApiKey | None:
    path = (
        f"api/v2/namespaces/{identifier(variables['namespaceId'])}/api-keys/"
        f"{identifier(variables['apiKeyId'])}"
    )
    try:
        wire = await request(rest, wire_models.ApiKeyDetail, method="GET", path=path)
    except APIError as error:
        if error.server_code == "NOT_FOUND_ERROR":
            return None
        raise
    return parse_model(ApiKey, wire.model_dump(mode="json"))


async def list(rest: AsyncRestV2Executor, namespace_id: str) -> tuple[ApiKey, ...]:
    path = f"api/v2/namespaces/{identifier(namespace_id)}/api-keys"
    items: builtins.list[ApiKey] = []
    previous: int | None = None
    before: str | None = None
    for _ in range(501):
        page = await request(
            rest,
            wire_models.ApiKeyList,
            method="GET",
            path=path,
            params=query_params({"limit": 20, "before_api_key_id": before}),
        )
        if len(page.items) > 20:
            raise ProtocolError("dicehub returned an invalid API-key listing.")
        for item in page.items:
            raw = item.api_key_id
            if not raw.isascii() or not raw.isdecimal() or len(raw) > 19:
                raise ProtocolError("dicehub returned an invalid API-key listing.")
            numeric = int(raw)
            if not 0 < numeric <= 2**63 - 1 or (previous is not None and numeric >= previous):
                raise ProtocolError("dicehub returned an invalid API-key listing.")
            previous = numeric
            items.append(parse_model(ApiKey, item.model_dump(mode="json")))
        if len(items) > 10000:
            raise ProtocolError("dicehub returned an invalid API-key listing.")
        if len(page.items) < 20:
            return tuple(items)
        before = page.items[-1].api_key_id
    raise ProtocolError("dicehub returned an invalid API-key listing.")


async def list_permissions(
    rest: AsyncRestV2Executor, variables: dict[str, object]
) -> tuple[NamespacePermission, ...]:
    path = f"api/v2/namespaces/{identifier(variables['namespaceId'])}/api-key-permissions"
    wire = await request(rest, wire_models.ApiKeyPermissionList, method="GET", path=path)
    if any(value not in NamespacePermission._value2member_map_ for value in wire.items):
        raise ProtocolError("dicehub returned invalid namespace permissions.")
    return tuple(NamespacePermission(value) for value in wire.items)


@async_mutation_outcome
async def update(rest: AsyncRestV2Executor, variables: dict[str, object]) -> ApiKey:
    path = (
        f"api/v2/namespaces/{identifier(variables['namespaceId'])}/api-keys/"
        f"{identifier(variables['apiKeyId'])}"
    )
    body = request_body({"name": variables["name"], "permissions": variables["permissions"]})
    wire = await request(rest, wire_models.ApiKeyDetail, method="PATCH", path=path, body=body)
    return parse_model(ApiKey, wire.model_dump(mode="json"))


@async_mutation_outcome
async def delete(rest: AsyncRestV2Executor, variables: dict[str, object]) -> None:
    path = f"api/v2/api-keys/{identifier(variables['apiKeyId'])}"
    await request(rest, wire_models.Done, method="DELETE", path=path)
