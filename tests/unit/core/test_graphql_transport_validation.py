from __future__ import annotations

import httpx
import pytest

from dicehub import (
    AuthenticationRequiredError,
    Client,
    ConfigurationError,
)


def test_rejects_missing_cookie() -> None:
    with pytest.raises(AuthenticationRequiredError):
        Client(base_url="https://dicehub.test", session_cookie="")


def test_rejects_missing_credentials() -> None:
    with pytest.raises(AuthenticationRequiredError):
        Client(base_url="https://dicehub.test")


def test_rejects_ambiguous_credentials() -> None:
    with pytest.raises(ConfigurationError, match="mutually exclusive"):
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            session_cookie="test-session-secret",
        )


def test_rejects_missing_api_key() -> None:
    with pytest.raises(AuthenticationRequiredError):
        Client(base_url="https://dicehub.test", api_key="")


@pytest.mark.parametrize(
    "api_key",
    [
        "bad value",
        "bad\tvalue",
        "bad\nvalue",
        "bad\rvalue",
        "bad\x00value",
        "bad\x1bvalue",
        "bad\x7fvalue",
        "nön-ascii",
        "x" * 4097,
    ],
)
def test_rejects_invalid_api_key_before_transport(api_key: str) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500, request=request)

    with pytest.raises(ConfigurationError) as captured:
        Client(
            base_url="https://dicehub.test",
            api_key=api_key,
            transport=httpx.MockTransport(handler),
        )

    assert requests == 0
    assert api_key not in str(captured.value)
    assert api_key not in str(captured.value.as_dict())


@pytest.mark.parametrize(
    "session_cookie",
    [
        "bad\x00value",
        "bad\tvalue",
        "bad\nvalue",
        "bad\rvalue",
        'bad"value',
        "bad,value",
        "bad;other=value",
        "bad\\value",
        "nön-ascii",
        "x" * 4097,
    ],
)
def test_rejects_cookie_header_injection(session_cookie: str) -> None:
    with pytest.raises(ConfigurationError) as captured:
        Client(base_url="https://dicehub.test", session_cookie=session_cookie)

    assert session_cookie not in str(captured.value)
    assert captured.value.__context__ is None


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ConfigurationError):
        Client(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            timeout=timeout,
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "http://dicehub.test",
        "https://user:password@dicehub.test",
        "https://dicehub.test/path",
        "https://dicehub.test?query=yes",
        "https://dicehub.test:bad",
        "https://[::1",
    ],
)
def test_rejects_unsafe_origins(base_url: str) -> None:
    with pytest.raises(ConfigurationError) as captured:
        Client(base_url=base_url, session_cookie="test-session-secret")

    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_allows_loopback_http() -> None:
    client = Client(
        base_url="http://127.0.0.1:8080",
        session_cookie="test-session-secret",
        transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request)),
    )
    client.close()


def test_api_key_rejects_unsafe_origin_before_transport_without_exposure() -> None:
    api_key = "sentinel-api-key"
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500, request=request)

    with pytest.raises(ConfigurationError) as captured:
        Client(
            base_url="http://attacker.example",
            api_key=api_key,
            transport=httpx.MockTransport(handler),
        )

    assert requests == 0
    assert api_key not in str(captured.value)
    assert api_key not in str(captured.value.as_dict())


def test_close_is_idempotent_and_use_after_close_is_typed() -> None:
    client = Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request)),
    )

    client.close()
    client.close()

    with pytest.raises(ConfigurationError, match="client is closed"):
        client.users.me()
