"""Private REST v2 read contract; HTTP ownership stays in the shared transports."""

from __future__ import annotations

import math
import re
from typing import Any, Literal, Protocol

import httpx

from dicehub.errors import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    HTTPError,
    ProtocolError,
)

ProjectReads = Literal["graphql", "rest_v2"]
ApiProtocol = Literal["graphql", "rest_v2"]
RestMethod = Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
RestParams = dict[str, str | int | list[str]]


class RestV2Executor(Protocol):
    def get_rest_v2(self, *, path: str, params: dict[str, str | int]) -> dict[str, Any]: ...

    def request_rest_v2(
        self,
        *,
        method: RestMethod,
        path: str,
        params: RestParams | None = None,
        body: dict[str, object] | None = None,
        max_response_bytes: int = 64 * 1024,
        timeout_cap: float | None = None,
    ) -> dict[str, Any]: ...


class AsyncRestV2Executor(Protocol):
    async def get_rest_v2(self, *, path: str, params: dict[str, str | int]) -> dict[str, Any]: ...

    async def request_rest_v2(
        self,
        *,
        method: RestMethod,
        path: str,
        params: RestParams | None = None,
        body: dict[str, object] | None = None,
        max_response_bytes: int = 64 * 1024,
        timeout_cap: float | None = None,
    ) -> dict[str, Any]: ...


def validate_project_reads(value: ProjectReads) -> None:
    if value not in ("graphql", "rest_v2"):
        raise ConfigurationError("Project reads must use graphql or rest_v2.")


def validate_rest_path(path: str) -> None:
    # Domain services supply fixed routes; user text is only in query/body values.
    if (
        not isinstance(path, str)
        or re.fullmatch(r"api/v2/[a-z0-9]+(?:[/-][a-z0-9]+)*", path) is None
    ):
        raise ConfigurationError("dicehub REST v2 path is invalid.")


def rest_timeout(timeout: float, cap: float | None) -> float:
    if cap is None:
        return timeout
    if (
        isinstance(cap, bool)
        or not isinstance(cap, (int, float))
        or not math.isfinite(cap)
        or cap <= 0
    ):
        raise ConfigurationError("Request timeout cap must be a positive finite number.")
    return min(timeout, float(cap))


def validate_api_protocol(value: ApiProtocol) -> None:
    if value not in ("graphql", "rest_v2"):
        raise ConfigurationError("API protocol must use graphql or rest_v2.")


def require_rest_success(response: httpx.Response) -> None:
    # Never decode error bodies: their messages and arbitrary codes are untrusted.
    status = response.status_code
    if status == 401:
        raise AuthenticationError("dicehub authentication failed.")
    if status == 403:
        raise APIError("dicehub rejected the operation.", server_code="PERMISSIONS_ERROR")
    if status == 404:
        raise APIError(
            "dicehub resource or REST v2 route was not found.", server_code="NOT_FOUND_ERROR"
        )
    if status == 422:
        raise APIError("dicehub rejected the request parameters.", server_code="VALIDATION_FAILED")
    if status not in {200, 201}:
        raise HTTPError(status)
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise ProtocolError("dicehub returned an unsupported REST v2 content type.")
