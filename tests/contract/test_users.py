from __future__ import annotations

import json

import httpx
import pytest

from dicehub import AuthenticationError, Client, ProtocolError, User


def _response(status: dict[str, object], user: dict[str, object] | None) -> dict[str, object]:
    return {"data": {"users": {"me": {"status": status, "user": user}}}}


def test_me_returns_typed_user_and_uses_fixed_operation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == "https://dicehub.test/api/graphql/"
        assert payload["operationName"] == "WhoAmI"
        assert "userId" in payload["query"]
        assert "username" in payload["query"]
        assert "email" not in payload["query"]
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(
            200,
            json=_response(
                {"succeeded": True, "error": None},
                {"userId": "42", "username": "ros"},
            ),
            request=request,
        )

    with Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=httpx.MockTransport(handler),
    ) as client:
        user = client.users.me()

    assert user == User(user_id="42", username="ros")
    assert user.model_dump() == {"user_id": "42", "username": "ros"}


def test_me_maps_dicehub_authentication_failure() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(
                {"succeeded": False, "error": "AUTH_ERROR"},
                None,
            ),
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            session_cookie="invalid-session",
            transport=transport,
        ) as client,
        pytest.raises(AuthenticationError),
    ):
        client.users.me()


def test_me_rejects_incompatible_success_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=_response(
                {"succeeded": True, "error": None},
                {"userId": 42, "username": "ros"},
            ),
            request=request,
        )
    )

    with (
        Client(
            base_url="https://dicehub.test",
            session_cookie="test-session-secret",
            transport=transport,
        ) as client,
        pytest.raises(ProtocolError),
    ):
        client.users.me()
