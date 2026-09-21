from __future__ import annotations

import asyncio
import json
import math
from collections.abc import AsyncIterable
from types import TracebackType
from typing import Any, BinaryIO, Literal, Protocol

import httpx

from dicehub._core.graphql import (
    _MAX_RESPONSE_BYTES,
    GraphQLResult,
    _decoded_object,
    _optional_content_length,
    _raise_for_http_status,
    _raise_for_rest_status,
    _require_fixed_relative_path,
    _require_identity_encoding,
    _validated_credentials,
    _validated_origin,
)
from dicehub.errors import (
    ConfigurationError,
    DiceHubError,
    GraphQLError,
    ProtocolError,
    TransportError,
)


class AsyncGraphQLExecutor(Protocol):
    """Minimal asynchronous interface consumed by domain services."""

    async def execute(
        self,
        *,
        operation_name: str,
        query: str,
        variables: dict[str, object] | None = None,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        timeout_cap: float | None = None,
    ) -> GraphQLResult: ...

    async def upload_binary(
        self,
        *,
        path: str,
        chunks: AsyncIterable[bytes],
        method: Literal["POST", "PUT"] = "PUT",
    ) -> dict[str, Any]: ...

    async def download_binary(
        self,
        *,
        path: str,
        destination: BinaryIO,
        max_bytes: int,
        content_label: str = "config file",
        expected_media_type: str | frozenset[str] | None = None,
    ) -> int: ...


class AsyncGraphQLTransport:
    """Private fixed-origin GraphQL transport using an asynchronous HTTP client."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        origin = _validated_origin(base_url)
        headers, cookies = _validated_credentials(
            api_key=api_key,
            session_cookie=session_cookie,
        )
        if not math.isfinite(timeout) or timeout <= 0:
            raise ConfigurationError("Timeout must be a positive finite number.")

        headers.update(
            {
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Content-Type": "application/json",
                "User-Agent": "dicehub-python",
            }
        )
        self._client = httpx.AsyncClient(
            base_url=origin,
            cookies=cookies,
            follow_redirects=False,
            headers=headers,
            timeout=timeout,
            transport=transport,
            trust_env=False,
        )
        self._timeout = timeout
        self._closed = False

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            await self._client.aclose()

    async def __aenter__(self) -> AsyncGraphQLTransport:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def execute(
        self,
        *,
        operation_name: str,
        query: str,
        variables: dict[str, object] | None = None,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        timeout_cap: float | None = None,
    ) -> GraphQLResult:
        if self._closed:
            raise ConfigurationError("dicehub client is closed.")
        request_timeout = self._timeout
        if timeout_cap is not None:
            if (
                isinstance(timeout_cap, bool)
                or not isinstance(timeout_cap, int | float)
                or not math.isfinite(timeout_cap)
                or timeout_cap <= 0
            ):
                raise ConfigurationError("Request timeout cap must be a positive finite number.")
            request_timeout = min(request_timeout, float(timeout_cap))

        mapped_error: DiceHubError | None = None
        try:
            async with self._client.stream(
                "POST",
                "api/graphql/",
                json={
                    "operationName": operation_name,
                    "query": query,
                    "variables": variables or {},
                },
                timeout=request_timeout,
            ) as response:
                _raise_for_http_status(response)
                content_encoding = response.headers.get("content-encoding", "identity")
                if content_encoding.strip().lower() not in {"", "identity"}:
                    raise ProtocolError("dicehub returned an unsupported content encoding.")
                content = await _read_limited(response, max_response_bytes)
        except httpx.TimeoutException:
            mapped_error = TransportError("The request to dicehub timed out.")
        except httpx.DecodingError:
            mapped_error = ProtocolError("dicehub returned an unsupported content encoding.")
        except httpx.RequestError:
            mapped_error = TransportError("Could not connect to dicehub.")
        if mapped_error is not None:
            raise mapped_error

        payload: Any = None
        malformed_json = False
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            malformed_json = True
        if malformed_json:
            raise ProtocolError("dicehub returned malformed JSON.")

        if not isinstance(payload, dict):
            raise ProtocolError("dicehub returned an invalid GraphQL response.")
        if payload.get("errors"):
            raise GraphQLError("The GraphQL operation failed.")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProtocolError("The GraphQL response did not contain data.")
        return GraphQLResult(data=data)

    async def upload_binary(
        self,
        *,
        path: str,
        chunks: AsyncIterable[bytes],
        method: Literal["POST", "PUT"] = "PUT",
    ) -> dict[str, Any]:
        if self._closed:
            raise ConfigurationError("dicehub client is closed.")
        if method not in {"POST", "PUT"}:
            raise ConfigurationError("Binary upload method is invalid.")
        _require_fixed_relative_path(path)

        mapped_error: DiceHubError | None = None
        try:
            async with self._client.stream(
                method,
                path,
                content=chunks,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/octet-stream",
                },
            ) as response:
                _raise_for_http_status(response)
                _require_identity_encoding(response)
                content = await _read_limited(response)
        except httpx.TimeoutException:
            mapped_error = TransportError("The request to dicehub timed out.")
        except httpx.DecodingError:
            mapped_error = ProtocolError("dicehub returned an unsupported content encoding.")
        except httpx.RequestError:
            mapped_error = TransportError("Could not connect to dicehub.")
        if mapped_error is not None:
            raise mapped_error

        payload = _decoded_object(content, "REST")
        _raise_for_rest_status(payload)
        return payload

    async def download_binary(
        self,
        *,
        path: str,
        destination: BinaryIO,
        max_bytes: int,
        content_label: str = "config file",
        expected_media_type: str | frozenset[str] | None = None,
    ) -> int:
        if self._closed:
            raise ConfigurationError("dicehub client is closed.")
        _require_fixed_relative_path(path)

        mapped_error: DiceHubError | None = None
        downloaded = 0
        try:
            async with self._client.stream(
                "GET",
                path,
                headers={"Accept": "application/octet-stream, application/json"},
            ) as response:
                _raise_for_http_status(response)
                _require_identity_encoding(response)
                media_type = response.headers.get("content-type", "").split(";", 1)[0]
                if media_type.strip().lower() == "application/json":
                    payload = _decoded_object(await _read_limited(response), "REST")
                    _raise_for_rest_status(payload)
                    raise ProtocolError(
                        f"dicehub returned JSON instead of {content_label} content."
                    )
                normalized_media_type = media_type.strip().lower()
                allowed_media_types = (
                    frozenset({expected_media_type})
                    if isinstance(expected_media_type, str)
                    else expected_media_type
                )
                if (
                    allowed_media_types is not None
                    and normalized_media_type not in allowed_media_types
                ):
                    raise ProtocolError(
                        f"dicehub returned an invalid {content_label} content type."
                    )
                declared_length = _optional_content_length(response)
                if declared_length is not None and declared_length > max_bytes:
                    raise ProtocolError(
                        f"dicehub returned {content_label} content larger than the configured "
                        "limit."
                    )
                async for chunk in response.aiter_bytes():
                    if downloaded + len(chunk) > max_bytes:
                        raise ProtocolError(
                            f"dicehub returned {content_label} content larger than the configured "
                            "limit."
                        )
                    written = await asyncio.to_thread(destination.write, chunk)
                    if written is not None and written != len(chunk):
                        raise ProtocolError(
                            f"The {content_label} destination accepted a partial write."
                        )
                    downloaded += len(chunk)
                if declared_length is not None and downloaded != declared_length:
                    raise ProtocolError(
                        f"dicehub returned an inconsistent {content_label} content length."
                    )
        except httpx.TimeoutException:
            mapped_error = TransportError("The request to dicehub timed out.")
        except httpx.DecodingError:
            mapped_error = ProtocolError("dicehub returned an unsupported content encoding.")
        except httpx.RequestError:
            mapped_error = TransportError("Could not connect to dicehub.")
        if mapped_error is not None:
            raise mapped_error
        return downloaded


async def _read_limited(response: httpx.Response, limit: int = _MAX_RESPONSE_BYTES) -> bytes:
    content = bytearray()
    async for chunk in response.aiter_bytes():
        if len(content) + len(chunk) > limit:
            if limit == _MAX_RESPONSE_BYTES:
                raise ProtocolError("dicehub returned a response larger than 64 KiB.")
            raise ProtocolError("dicehub returned a response larger than the permitted limit.")
        content.extend(chunk)
    return bytes(content)
