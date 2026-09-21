from __future__ import annotations

import httpx
import pytest

from dicehub import (
    AuthenticationError,
    Client,
    GraphQLError,
    HTTPError,
    ProtocolError,
    TransportError,
)


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=handler,
    )


def test_maps_http_failure_without_response_body() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            503,
            text="sensitive upstream response",
            headers={"x-request-id": "req-123"},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(HTTPError) as captured:
        client.users.me()

    assert captured.value.status_code == 503
    assert captured.value.request_id is None
    assert captured.value.retryable is True
    assert "sensitive" not in str(captured.value)
    assert "req-123" not in str(captured.value.as_dict())


@pytest.mark.parametrize("status_code", [401, 403])
def test_maps_http_authentication_failure(status_code: int) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code, request=request))

    with _client(transport) as client, pytest.raises(AuthenticationError):
        client.users.me()


def test_does_not_follow_redirects() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"location": "https://other.example/api/graphql/"},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(HTTPError):
        client.users.me()

    assert len(requests) == 1


def test_maps_malformed_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="not-json", request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.users.me()

    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize("payload", [[], {"extensions": {}}])
def test_rejects_invalid_graphql_envelopes(payload: object) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload, request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.users.me()


def test_rejects_encoded_response_without_decoding_it() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"not-actually-compressed",
            headers={"content-encoding": "gzip"},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.users.me()

    assert "content encoding" in str(captured.value)


def test_rejects_response_larger_than_limit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b" " * (64 * 1024 + 1), request=request)
    )

    with _client(transport) as client, pytest.raises(ProtocolError) as captured:
        client.users.me()

    assert "larger than 64 KiB" in str(captured.value)


def test_maps_graphql_errors_without_exposing_server_message() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"errors": [{"message": "sensitive internal detail"}]},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(GraphQLError) as captured:
        client.users.me()

    assert "sensitive" not in str(captured.value)


def test_maps_timeout() -> None:
    sentinel = "timeout with sensitive detail"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(sentinel, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(TransportError) as captured,
    ):
        client.users.me()

    assert sentinel not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_maps_connection_failure_without_transport_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive transport detail", request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(TransportError) as captured,
    ):
        client.users.me()

    assert "sensitive" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None
