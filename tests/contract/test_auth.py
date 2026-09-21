from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from dicehub import (
    APIError,
    AsyncClient,
    AuthContext,
    AuthenticationError,
    Client,
    HTTPError,
    IdentityMode,
    ProtocolError,
    TransportError,
)


def _response(
    *,
    mode: object = "API_KEY",
    succeeded: object = True,
    error: object = None,
    auth_context: object = ...,
) -> dict[str, object]:
    if auth_context is ...:
        auth_context = {"identityMode": mode}
    return {
        "data": {
            "authentications": {
                "getAuthContext": {
                    "status": {"succeeded": succeeded, "error": error},
                    "authContext": auth_context,
                }
            }
        }
    }


def test_client_uses_hosted_origin_by_default() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://dicehub.com/api/graphql/"
        return httpx.Response(200, json=_response(), request=request)

    with Client(
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.auth.context().identity_mode is IdentityMode.API_KEY


def test_async_client_uses_hosted_origin_by_default() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://dicehub.com/api/graphql/"
        return httpx.Response(200, json=_response(), request=request)

    async def scenario() -> None:
        async with AsyncClient(
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client:
            context = await client.auth.context()
            assert context.identity_mode is IdentityMode.API_KEY

    asyncio.run(scenario())


def test_context_uses_only_bearer_header_and_returns_typed_mode() -> None:
    api_key = "sentinel-api-key"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert request.url.params.get("api_key") is None
        assert request.headers.get_list("authorization") == [f"Bearer {api_key}"]
        assert "cookie" not in request.headers
        assert payload["operationName"] == "GetAuthContext"
        assert "getAuthContext" in payload["query"]
        assert "identityMode" in payload["query"]
        assert "apiKey" not in payload["query"]
        assert payload["variables"] == {}
        assert api_key not in request.content.decode()
        return httpx.Response(200, json=_response(), request=request)

    with Client(
        base_url="https://dicehub.test",
        api_key=api_key,
        transport=httpx.MockTransport(handler),
    ) as client:
        context = client.auth.context()

    assert context == AuthContext(identity_mode=IdentityMode.API_KEY)
    assert context.model_dump(mode="json") == {"identity_mode": "API_KEY"}
    assert api_key not in repr(context)


def test_context_supports_the_session_development_bridge() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        return httpx.Response(
            200,
            json=_response(mode="SESSION"),
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        context = client.auth.context()

    assert context.identity_mode is IdentityMode.SESSION


@pytest.mark.parametrize("mode", ["SESSION", "CLIENT_ID", "ANONYMOUS"])
def test_api_key_requires_api_key_identity_mode(mode: str) -> None:
    api_key = "sentinel-api-key"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(mode=mode),
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key=api_key,
            transport=transport,
        ) as client,
        pytest.raises(AuthenticationError) as captured,
    ):
        client.auth.context()

    assert captured.value.code == "AUTH_FAILED"
    assert api_key not in str(captured.value)
    assert api_key not in json.dumps(captured.value.as_dict())


@pytest.mark.parametrize(
    "response",
    [
        _response(mode="FUTURE_MODE"),
        _response(auth_context=None),
        _response(mode=1),
        {
            "data": {
                "authentications": {
                    "getAuthContext": {
                        "status": {"succeeded": True, "error": None},
                        "authContext": {
                            "identityMode": "API_KEY",
                            "apiKeyDigest": "must-not-be-accepted",
                        },
                    }
                }
            }
        },
    ],
)
def test_context_rejects_incompatible_success_payload(response: dict[str, object]) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=response, request=request)
    )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=transport,
        ) as client,
        pytest.raises(ProtocolError) as captured,
    ):
        client.auth.context()

    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_context_maps_status_failure_without_server_details(
    server_error: str,
    error_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(succeeded=False, error=server_error, auth_context=None),
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=transport,
        ) as client,
        pytest.raises(error_type) as captured,
    ):
        client.auth.context()

    assert server_error not in str(captured.value)


def test_api_key_does_not_follow_cross_origin_redirect() -> None:
    api_key = "sentinel-api-key"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            307,
            headers={"location": "https://attacker.example/capture"},
            request=request,
        )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key=api_key,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(HTTPError) as captured,
    ):
        client.auth.context()

    assert len(requests) == 1
    assert api_key not in str(captured.value)


@pytest.mark.parametrize("status_code", [401, 403])
def test_api_key_http_auth_failure_redacts_credentials_and_body(status_code: int) -> None:
    api_key = "sentinel-api-key"
    server_secret = "sentinel-server-secret"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            text=server_secret,
            headers={"x-debug-detail": server_secret},
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            api_key=api_key,
            transport=transport,
        ) as client,
        pytest.raises(AuthenticationError) as captured,
    ):
        client.auth.context()

    exposed = str(captured.value) + json.dumps(captured.value.as_dict())
    assert api_key not in exposed
    assert server_secret not in exposed


def test_api_key_transport_error_does_not_expose_httpx_detail() -> None:
    api_key = "sentinel-api-key"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"transport failed with {api_key}", request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key=api_key,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(TransportError) as captured,
    ):
        client.auth.context()

    assert api_key not in str(captured.value)
    assert api_key not in str(captured.value.as_dict())


def test_accepts_api_key_at_length_limit() -> None:
    api_key = "x" * 4096
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=_response(), request=request)
    )

    with Client(
        base_url="https://dicehub.test",
        api_key=api_key,
        transport=transport,
    ) as client:
        context = client.auth.context()

    assert context.identity_mode is IdentityMode.API_KEY
