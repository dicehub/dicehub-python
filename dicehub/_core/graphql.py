from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, BinaryIO, Literal, Protocol

import httpx

from dicehub.errors import (
    APIError,
    AuthenticationError,
    AuthenticationRequiredError,
    ConfigurationError,
    DiceHubError,
    GraphQLError,
    HTTPError,
    ProtocolError,
    TransportError,
)

_MAX_RESPONSE_BYTES = 64 * 1024
_MAX_API_KEY_LENGTH = 4096
_MAX_SESSION_COOKIE_LENGTH = 4096
_PUBLIC_REST_ERROR_CODES = frozenset({"AUTH_ERROR", "PERMISSIONS_ERROR"})


@dataclass(frozen=True)
class GraphQLResult:
    data: dict[str, Any]


class GraphQLExecutor(Protocol):
    """Minimal interface consumed by domain services."""

    def execute(
        self,
        *,
        operation_name: str,
        query: str,
        variables: dict[str, object] | None = None,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        timeout_cap: float | None = None,
    ) -> GraphQLResult: ...

    def upload_binary(
        self,
        *,
        path: str,
        chunks: Iterable[bytes],
        method: Literal["POST", "PUT"] = "PUT",
    ) -> dict[str, Any]: ...

    def download_binary(
        self,
        *,
        path: str,
        destination: BinaryIO,
        max_bytes: int,
        content_label: str = "config file",
        expected_media_type: str | frozenset[str] | None = None,
    ) -> int: ...


class GraphQLTransport:
    """Private fixed-origin GraphQL transport."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        session_cookie: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
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
        self._client = httpx.Client(
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

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    def execute(
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
            with self._client.stream(
                "POST",
                "api/graphql/",
                json={
                    "operationName": operation_name,
                    "query": query,
                    "variables": variables or {},
                },
                timeout=request_timeout,
            ) as response:
                if response.status_code in {401, 403}:
                    raise AuthenticationError("dicehub authentication failed.")
                if not 200 <= response.status_code < 300:
                    raise HTTPError(response.status_code)
                content_encoding = response.headers.get("content-encoding", "identity")
                if content_encoding.strip().lower() not in {"", "identity"}:
                    raise ProtocolError("dicehub returned an unsupported content encoding.")
                content = _read_limited(response, max_response_bytes)
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

    def upload_binary(
        self,
        *,
        path: str,
        chunks: Iterable[bytes],
        method: Literal["POST", "PUT"] = "PUT",
    ) -> dict[str, Any]:
        if self._closed:
            raise ConfigurationError("dicehub client is closed.")
        if method not in {"POST", "PUT"}:
            raise ConfigurationError("Binary upload method is invalid.")
        _require_fixed_relative_path(path)

        mapped_error: DiceHubError | None = None
        try:
            with self._client.stream(
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
                content = _read_limited(response)
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

    def download_binary(
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
            with self._client.stream(
                "GET",
                path,
                headers={"Accept": "application/octet-stream, application/json"},
            ) as response:
                _raise_for_http_status(response)
                _require_identity_encoding(response)
                media_type = response.headers.get("content-type", "").split(";", 1)[0]
                if media_type.strip().lower() == "application/json":
                    payload = _decoded_object(_read_limited(response), "REST")
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
                for chunk in response.iter_bytes():
                    if downloaded + len(chunk) > max_bytes:
                        raise ProtocolError(
                            f"dicehub returned {content_label} content larger than the configured "
                            "limit."
                        )
                    written = destination.write(chunk)
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


def _read_limited(response: httpx.Response, limit: int = _MAX_RESPONSE_BYTES) -> bytes:
    content = bytearray()
    for chunk in response.iter_bytes():
        if len(content) + len(chunk) > limit:
            if limit == _MAX_RESPONSE_BYTES:
                raise ProtocolError("dicehub returned a response larger than 64 KiB.")
            raise ProtocolError("dicehub returned a response larger than the permitted limit.")
        content.extend(chunk)
    return bytes(content)


def _raise_for_http_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise AuthenticationError("dicehub authentication failed.")
    if not 200 <= response.status_code < 300:
        raise HTTPError(response.status_code)


def _require_identity_encoding(response: httpx.Response) -> None:
    content_encoding = response.headers.get("content-encoding", "identity")
    if content_encoding.strip().lower() not in {"", "identity"}:
        raise ProtocolError("dicehub returned an unsupported content encoding.")


def _optional_content_length(response: httpx.Response) -> int | None:
    value = response.headers.get("content-length")
    if value is None:
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 20:
        raise ProtocolError("dicehub returned an invalid content length.")
    return int(value)


def _decoded_object(content: bytes, protocol: str) -> dict[str, Any]:
    payload: Any = None
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    if not isinstance(payload, dict):
        raise ProtocolError(f"dicehub returned an invalid {protocol} response.")
    return payload


def _raise_for_rest_status(payload: dict[str, Any]) -> None:
    status = payload.get("status")
    if not isinstance(status, dict) or not isinstance(status.get("succeeded"), bool):
        raise ProtocolError("dicehub returned an invalid REST response.")
    if not status["succeeded"]:
        server_code = status.get("error")
        raise APIError(
            "dicehub rejected the operation.",
            server_code=(
                server_code
                if isinstance(server_code, str) and server_code in _PUBLIC_REST_ERROR_CODES
                else None
            ),
        )


def _require_fixed_relative_path(path: str) -> None:
    if (
        not isinstance(path, str)
        or not path.startswith("api/")
        or path.startswith("/")
        or "?" in path
        or "#" in path
        or "://" in path
        or "\\" in path
        or any(not character.isprintable() for character in path)
    ):
        raise ConfigurationError("dicehub REST path is invalid.")


def _validated_origin(base_url: str) -> str:
    url: httpx.URL | None = None
    try:
        url = httpx.URL(base_url)
    except (TypeError, ValueError, httpx.InvalidURL):
        pass
    if url is None:
        raise ConfigurationError("dicehub URL is invalid.")

    if url.scheme not in {"http", "https"} or url.host is None:
        raise ConfigurationError("dicehub URL must be an HTTP or HTTPS origin.")
    if url.username or url.password:
        raise ConfigurationError("dicehub URL must not contain credentials.")
    if url.query or url.fragment or url.path not in {"", "/"}:
        raise ConfigurationError("dicehub URL must not contain a path, query, or fragment.")
    if url.scheme == "http" and url.host not in {"127.0.0.1", "::1", "localhost"}:
        raise ConfigurationError("Plain HTTP is allowed only for exact loopback hosts.")

    return str(url.copy_with(path="/"))


def _validated_credentials(
    *,
    api_key: str | None,
    session_cookie: str | None,
) -> tuple[dict[str, str], dict[str, str] | None]:
    if api_key is None and session_cookie is None:
        raise AuthenticationRequiredError("An API key or session cookie is required.")
    if api_key is not None and session_cookie is not None:
        raise ConfigurationError("API key and session cookie are mutually exclusive.")
    if api_key is not None:
        return {"Authorization": f"Bearer {_validated_api_key(api_key)}"}, None
    assert session_cookie is not None
    return {}, {"_dicehub_session": _validated_cookie(session_cookie)}


def _validated_api_key(api_key: str) -> str:
    if not api_key:
        raise AuthenticationRequiredError("An API key is required.")
    if len(api_key) > _MAX_API_KEY_LENGTH or any(
        not 0x21 <= ord(character) <= 0x7E for character in api_key
    ):
        raise ConfigurationError("dicehub API key contains invalid characters.")
    return api_key


def _validated_cookie(session_cookie: str) -> str:
    if not session_cookie:
        raise AuthenticationRequiredError("A session cookie is required.")
    if len(session_cookie) > _MAX_SESSION_COOKIE_LENGTH or any(
        not _is_cookie_octet(character) for character in session_cookie
    ):
        raise ConfigurationError("dicehub session cookie contains invalid characters.")
    return session_cookie


def _is_cookie_octet(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint == 0x21
        or 0x23 <= codepoint <= 0x2B
        or 0x2D <= codepoint <= 0x3A
        or 0x3C <= codepoint <= 0x5B
        or 0x5D <= codepoint <= 0x7E
    )
