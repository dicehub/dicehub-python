"""Typed REST requests using the existing fixed-origin transport."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from dicehub._core.rest_models import parse_model
from dicehub._core.rest_v2 import AsyncRestV2Executor, RestMethod, RestParams, RestV2Executor

ModelT = TypeVar("ModelT", bound=BaseModel)


def request(
    rest: RestV2Executor,
    model: type[ModelT],
    *,
    method: RestMethod,
    path: str,
    params: RestParams | None = None,
    body: dict[str, object] | None = None,
    max_response_bytes: int = 64 * 1024,
    timeout_cap: float | None = None,
) -> ModelT:
    data = rest.request_rest_v2(
        method=method,
        path=path,
        params=params,
        body=body,
        max_response_bytes=max_response_bytes,
        timeout_cap=timeout_cap,
    )
    return parse_model(model, data)


async def async_request(
    rest: AsyncRestV2Executor,
    model: type[ModelT],
    *,
    method: RestMethod,
    path: str,
    params: RestParams | None = None,
    body: dict[str, object] | None = None,
    max_response_bytes: int = 64 * 1024,
    timeout_cap: float | None = None,
) -> ModelT:
    data = await rest.request_rest_v2(
        method=method,
        path=path,
        params=params,
        body=body,
        max_response_bytes=max_response_bytes,
        timeout_cap=timeout_cap,
    )
    return parse_model(model, data)
