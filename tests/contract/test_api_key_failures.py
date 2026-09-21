from __future__ import annotations

import httpx
import pytest

from dicehub import (
    Client,
    MutationOutcomeUnknownError,
    NamespacePermission,
    ProtocolError,
)


def _status() -> dict[str, object]:
    return {"succeeded": True, "error": None}


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=handler,
    )


def _api_key(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "apiKeyId": "91",
        "name": "ci agent",
        "prefix": "12345",
        "permissions": ["VIEW_USER_PROFILE"],
        "createdAt": "2026-08-11T09:10:11.123",
        "updatedAt": "2026-08-11T10:11:12.456Z",
        "lastUsedAt": None,
        "status": "ACTIVE",
        "notBefore": None,
        "expiresAt": None,
        "validityStatus": "ACTIVE",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("failure", ["transport", "http", "graphql", "protocol"])
def test_mutation_ambiguity_is_not_retried_or_leaked(
    operation: str,
    failure: str,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if failure == "transport":
            raise httpx.ConnectError("sentinel transport details", request=request)
        if failure == "http":
            return httpx.Response(503, text="sentinel server body", request=request)
        if failure == "graphql":
            return httpx.Response(
                200,
                json={"errors": [{"message": "sentinel GraphQL details"}]},
                request=request,
            )
        return httpx.Response(200, json={"data": {"apiKeys": {}}}, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        if operation == "create":
            client.api_keys.create(
                namespace_id="42",
                name="ci agent",
                permissions=[NamespacePermission.VIEW_USER_PROFILE],
            )
        elif operation == "update":
            client.api_keys.update(
                namespace_id="42",
                api_key_id="91",
                name="ci agent",
            )
        else:
            client.api_keys.delete(api_key_id="91")

    assert request_count == 1
    assert captured.value.retryable is False
    assert "sentinel" not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


def test_update_success_without_metadata_has_unknown_outcome() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"data": {"apiKeys": {"updateApiKey": {"status": _status(), "apiKey": None}}}},
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(MutationOutcomeUnknownError):
        client.api_keys.update(namespace_id="42", api_key_id="91", name="ci agent")


@pytest.mark.parametrize(
    "api_key",
    [
        None,
        {**_api_key(), "value": None},
        {**_api_key(apiKeyId=91), "value": "safe-secret"},
        {**_api_key(), "value": "safe-secret", "digest": "must-not-be-accepted"},
        {**_api_key(apiKeyId="01"), "value": "safe-secret"},
        {**_api_key(name="ci/agent"), "value": "safe-secret"},
        {**_api_key(prefix="bad prefix"), "value": "safe-secret"},
        {**_api_key(permissions=["UNKNOWN"]), "value": "safe-secret"},
        {**_api_key(status="REVOKED"), "value": "safe-secret"},
        {**_api_key(createdAt=None), "value": "safe-secret"},
    ],
)
def test_create_rejects_incompatible_success_payload(api_key: object) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "createApiKey": {
                            "status": _status(),
                            "apiKey": api_key,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(MutationOutcomeUnknownError):
        client.api_keys.create(
            namespace_id="42",
            name="ci agent",
            permissions=[NamespacePermission.VIEW_USER_PROFILE],
        )


@pytest.mark.parametrize(
    "secret",
    ["contains space", "line\nbreak", "snowman-\N{SNOWMAN}", "\x1b[2J"],
)
def test_create_rejects_unsafe_secret_without_reflecting_it(secret: str) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "createApiKey": {
                            "status": _status(),
                            "apiKey": {**_api_key(), "value": secret},
                        }
                    }
                }
            },
            request=request,
        )
    )

    with (
        _client(transport) as client,
        pytest.raises(MutationOutcomeUnknownError) as captured,
    ):
        client.api_keys.create(
            namespace_id="42",
            name="ci agent",
            permissions=[NamespacePermission.VIEW_USER_PROFILE],
        )

    assert secret not in str(captured.value)
    assert captured.value.__context__ is None
    assert captured.value.__cause__ is None


@pytest.mark.parametrize(
    "api_keys",
    [
        None,
        [{**_api_key(), "value": None}],
        [_api_key(name=None)],
        [_api_key(apiKeyId="01")],
        [_api_key(name="\x1b[2J")],
        [_api_key(prefix="bad prefix")],
        [_api_key(permissions=["VIEW_RUN_INFO", "VIEW_RUN_INFO"])],
        [_api_key(lastUsedAt="not-a-timestamp")],
        [_api_key(expiresAt="0001-01-01T00:00:00+14:00")],
    ],
)
def test_list_rejects_incompatible_success_payload(api_keys: object) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "listApiKeys": {
                            "status": _status(),
                            "apiKeys": api_keys,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with _client(transport) as client, pytest.raises(ProtocolError):
        client.api_keys.list(namespace_id="42")
