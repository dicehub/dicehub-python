from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from pydantic import SecretStr

from dicehub import (
    APIError,
    ApiKey,
    ApiKeyStatus,
    ApiKeyValidityStatus,
    AuthenticationError,
    Client,
    CreatedApiKey,
    NamespacePermission,
)

CREATED_AT = "2026-08-11T09:10:11.123"
UPDATED_AT = "2026-08-11T10:11:12.456Z"
LAST_USED_AT = "2026-08-11T12:11:13.789+02:00"
EXPIRES_AT = "2026-09-11T12:11:13.789Z"


def _status(*, succeeded: bool = True, error: str | None = None) -> dict[str, object]:
    return {"succeeded": succeeded, "error": error}


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
        "permissions": ["VIEW_USER_PROFILE", "VIEW_PROJECT_INFO"],
        "createdAt": CREATED_AT,
        "updatedAt": UPDATED_AT,
        "lastUsedAt": LAST_USED_AT,
        "status": "ACTIVE",
        "notBefore": None,
        "expiresAt": None,
        "validityStatus": "ACTIVE",
    }
    payload.update(overrides)
    return payload


def _expected_api_key(**overrides: object) -> ApiKey:
    payload: dict[str, object] = {
        "api_key_id": "91",
        "name": "ci agent",
        "prefix": "12345",
        "permissions": (
            NamespacePermission.VIEW_USER_PROFILE,
            NamespacePermission.VIEW_PROJECT_INFO,
        ),
        "created_at": datetime.fromisoformat(CREATED_AT).replace(tzinfo=timezone.utc),
        "updated_at": datetime.fromisoformat(UPDATED_AT.replace("Z", "+00:00")),
        "last_used_at": datetime(2026, 8, 11, 10, 11, 13, 789000, tzinfo=timezone.utc),
        "status": ApiKeyStatus.ACTIVE,
        "not_before": None,
        "expires_at": None,
        "validity_status": ApiKeyValidityStatus.ACTIVE,
    }
    payload.update(overrides)
    return ApiKey.model_validate(payload)


def test_create_uses_fixed_operation_and_returns_secret_once() -> None:
    secret = "12345678-1234-5678-9234-567812345678"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "CreateApiKey"
        assert payload["variables"] == {
            "namespaceId": "42",
            "name": "ci agent",
            "permissions": ["VIEW_USER_PROFILE", "VIEW_PROJECT_INFO"],
            "notBefore": None,
            "expiresAt": None,
        }
        assert "createApiKey" in payload["query"]
        assert "value" in payload["query"]
        assert request.headers["cookie"] == "_dicehub_session=test-session-secret"
        return httpx.Response(
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

    with _client(httpx.MockTransport(handler)) as client:
        created = client.api_keys.create(
            namespace_id="42",
            name="  ci agent  ",
            permissions=[
                NamespacePermission.VIEW_USER_PROFILE,
                NamespacePermission.VIEW_PROJECT_INFO,
            ],
        )

    assert created == CreatedApiKey(**_expected_api_key().model_dump(), value=SecretStr(secret))
    assert created.value.get_secret_value() == secret
    assert secret not in repr(created)
    assert secret not in created.model_dump_json()


def test_create_accepts_app_membership_permissions() -> None:
    requested_permissions = [
        NamespacePermission.VIEW_PUBLIC_APP_MEMBERS,
        NamespacePermission.VIEW_PRIVATE_APP_MEMBERS,
        NamespacePermission.MANAGE_APP_MEMBERS,
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"]["permissions"] == [
            "VIEW_PUBLIC_APP_MEMBERS",
            "VIEW_PRIVATE_APP_MEMBERS",
            "MANAGE_APP_MEMBERS",
        ]
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "createApiKey": {
                            "status": _status(),
                            "apiKey": {
                                **_api_key(
                                    permissions=[
                                        permission.value for permission in requested_permissions
                                    ]
                                ),
                                "value": "one-time-secret",
                            },
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        created = client.api_keys.create(
            namespace_id="42",
            name="app member agent",
            permissions=requested_permissions,
        )

    assert created.permissions == tuple(requested_permissions)


def test_create_sends_normalized_validity_timestamps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"]["notBefore"] == "2026-08-17T07:00:00.000Z"
        assert payload["variables"]["expiresAt"] == "2026-09-17T07:00:00.000Z"
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "createApiKey": {
                            "status": _status(),
                            "apiKey": {
                                **_api_key(
                                    notBefore="2026-08-17T07:00:00Z",
                                    expiresAt="2026-09-17T07:00:00Z",
                                    validityStatus="NOT_YET_ACTIVE",
                                ),
                                "value": "one-time-secret",
                            },
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        created = client.api_keys.create(
            namespace_id="42",
            name="scheduled agent",
            permissions=[NamespacePermission.VIEW_PROJECT_INFO],
            not_before=datetime.fromisoformat("2026-08-17T09:00:00+02:00"),
            expires_at=datetime.fromisoformat("2026-09-17T09:00:00+02:00"),
        )

    assert created.not_before == datetime(2026, 8, 17, 7, tzinfo=timezone.utc)
    assert created.expires_at == datetime(2026, 9, 17, 7, tzinfo=timezone.utc)
    assert created.validity_status is ApiKeyValidityStatus.NOT_YET_ACTIVE


def test_list_returns_immutable_metadata_without_requesting_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListApiKeys"
        assert payload["variables"] == {
            "namespaceId": "42",
            "beforeApiKeyId": None,
            "limit": 20,
        }
        assert "listApiKeys" in payload["query"]
        assert "value" not in payload["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "listApiKeys": {
                            "status": _status(),
                            "apiKeys": [
                                {
                                    **_api_key(apiKeyId="92"),
                                },
                                {
                                    **_api_key(
                                        apiKeyId="91",
                                        name="runner",
                                        prefix="87654",
                                        permissions=["VIEW_RUN_INFO"],
                                        lastUsedAt=None,
                                    ),
                                },
                            ],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        api_keys = client.api_keys.list(namespace_id="42")

    assert api_keys == (
        _expected_api_key(api_key_id="92"),
        _expected_api_key(
            api_key_id="91",
            name="runner",
            prefix="87654",
            permissions=(NamespacePermission.VIEW_RUN_INFO,),
            last_used_at=None,
        ),
    )
    assert all(not hasattr(api_key, "value") for api_key in api_keys)


def test_list_can_return_no_api_keys() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"data": {"apiKeys": {"listApiKeys": {"status": _status(), "apiKeys": []}}}},
            request=request,
        )
    )

    with _client(transport) as client:
        assert client.api_keys.list(namespace_id="42") == ()


def test_get_uses_fixed_operation_and_preserves_missing_as_none() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        payload = json.loads(request.content)
        assert payload["operationName"] == "GetApiKey"
        assert payload["variables"] == {"namespaceId": "42", "apiKeyId": "91"}
        assert "getApiKey" in payload["query"]
        assert "value" not in payload["query"]
        api_key = _api_key() if request_count == 1 else None
        return httpx.Response(
            200,
            json={"data": {"apiKeys": {"getApiKey": {"status": _status(), "apiKey": api_key}}}},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        assert client.api_keys.get(namespace_id="42", api_key_id="91") == _expected_api_key()
        assert client.api_keys.get(namespace_id="42", api_key_id="91") is None


def test_list_permissions_returns_server_order_without_local_expansion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "ListApiKeyPermissions"
        assert payload["variables"] == {"namespaceId": "42"}
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "listApiKeyPermissions": {
                            "status": _status(),
                            "permissions": ["VIEW_RUN_INFO", "VIEW_PROJECT_INFO"],
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        permissions = client.api_keys.list_permissions(namespace_id="42")

    assert permissions == (
        NamespacePermission.VIEW_RUN_INFO,
        NamespacePermission.VIEW_PROJECT_INFO,
    )


def test_update_uses_fixed_operation_and_never_requests_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "UpdateApiKey"
        assert payload["variables"] == {
            "namespaceId": "42",
            "apiKeyId": "91",
            "name": "renamed agent",
            "permissions": ["VIEW_RUN_INFO"],
        }
        assert "updateApiKey" in payload["query"]
        assert "value" not in payload["query"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "updateApiKey": {
                            "status": _status(),
                            "apiKey": _api_key(
                                name="renamed agent",
                                permissions=["VIEW_RUN_INFO"],
                            ),
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        updated = client.api_keys.update(
            namespace_id="42",
            api_key_id="91",
            name="  renamed agent  ",
            permissions=[NamespacePermission.VIEW_RUN_INFO],
        )

    assert updated == _expected_api_key(
        name="renamed agent",
        permissions=(NamespacePermission.VIEW_RUN_INFO,),
    )
    assert not hasattr(updated, "value")


def test_update_none_permissions_preserves_grants_via_explicit_null() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["variables"]["permissions"] is None
        return httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "updateApiKey": {
                            "status": _status(),
                            "apiKey": _api_key(name="renamed agent"),
                        }
                    }
                }
            },
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        updated = client.api_keys.update(namespace_id="42", api_key_id="91", name="renamed agent")

    assert updated.permissions == _expected_api_key().permissions


def test_delete_uses_fixed_operation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["operationName"] == "DeleteApiKey"
        assert payload["variables"] == {"apiKeyId": "91"}
        assert "deleteApiKey" in payload["query"]
        return httpx.Response(
            200,
            json={"data": {"apiKeys": {"deleteApiKey": {"status": _status()}}}},
            request=request,
        )

    with _client(httpx.MockTransport(handler)) as client:
        client.api_keys.delete(api_key_id="91")


@pytest.mark.parametrize(
    ("server_error", "error_type"),
    [("AUTH_ERROR", AuthenticationError), ("sentinel-server-secret", APIError)],
)
def test_create_maps_status_failure_without_server_details(
    server_error: str,
    error_type: type[Exception],
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "createApiKey": {
                            "status": _status(succeeded=False, error=server_error),
                            "apiKey": None,
                        }
                    }
                }
            },
            request=request,
        )
    )

    with (
        _client(transport) as client,
        pytest.raises(error_type) as captured,
    ):
        client.api_keys.create(
            namespace_id="42",
            name="ci agent",
            permissions=[NamespacePermission.VIEW_USER_PROFILE],
        )

    assert server_error not in str(captured.value)


def test_delete_maps_authentication_failure() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "apiKeys": {
                        "deleteApiKey": {"status": _status(succeeded=False, error="AUTH_ERROR")}
                    }
                }
            },
            request=request,
        )
    )

    with (
        _client(transport) as client,
        pytest.raises(AuthenticationError),
    ):
        client.api_keys.delete(api_key_id="91")
