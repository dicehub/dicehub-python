from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import cast

import httpx
import pytest
from pydantic import ValidationError

from dicehub import (
    ApiKey,
    ApiKeyStatus,
    ApiKeyValidityStatus,
    Client,
    ConfigurationError,
    NamespacePermission,
)
from dicehub.api_keys._validation import validated_name


def _client(handler: httpx.MockTransport) -> Client:
    return Client(
        base_url="https://dicehub.test",
        session_cookie="test-session-secret",
        transport=handler,
    )


@pytest.mark.parametrize(
    "namespace_id",
    ["", "0", "01", "+42", "-91", "project", " 42", "42 ", "x\n42", "x" * 257],
)
def test_namespace_id_validation_happens_before_transport(namespace_id: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError),
    ):
        client.api_keys.list(namespace_id=namespace_id)

    assert request_count == 0


def test_api_key_id_validation_happens_before_transport() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError),
    ):
        client.api_keys.delete(api_key_id="01")

    assert request_count == 0


@pytest.mark.parametrize(
    "name",
    ["", "   ", "ci/agent", "agent/", "ci\nagent", "x" * 121],
)
def test_name_validation_happens_before_transport(name: str) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError),
    ):
        client.api_keys.create(
            namespace_id="42",
            name=name,
            permissions=[NamespacePermission.VIEW_USER_PROFILE],
        )

    assert request_count == 0


def test_name_validation_matches_server_normalization_and_boundary() -> None:
    boundary_name = "x" * 120

    assert validated_name(f"  {boundary_name}  ") == boundary_name


def test_api_key_preserves_original_three_field_construction() -> None:
    api_key = ApiKey(api_key_id="91", name="ci agent", prefix="12345")

    assert api_key.permissions == ()
    assert api_key.created_at is None
    assert api_key.updated_at is None
    assert api_key.last_used_at is None
    assert api_key.status is ApiKeyStatus.ACTIVE
    assert api_key.not_before is None
    assert api_key.expires_at is None
    assert api_key.validity_status is ApiKeyValidityStatus.ACTIVE


@pytest.mark.parametrize(
    ("not_before", "expires_at"),
    [
        (datetime(2026, 8, 17, 9), None),
        (None, datetime(2026, 8, 17, 9, 0, 0, 1, tzinfo=timezone.utc)),
        (
            datetime(2026, 8, 18, tzinfo=timezone.utc),
            datetime(2026, 8, 17, tzinfo=timezone.utc),
        ),
        (
            datetime.min.replace(tzinfo=timezone(timedelta(hours=14))),
            None,
        ),
    ],
)
def test_validity_validation_happens_before_transport(
    not_before: datetime | None,
    expires_at: datetime | None,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError),
    ):
        client.api_keys.create(
            namespace_id="42",
            name="ci agent",
            permissions=[NamespacePermission.VIEW_USER_PROFILE],
            not_before=not_before,
            expires_at=expires_at,
        )

    assert request_count == 0


def test_public_api_key_rejects_naive_metadata_timestamp() -> None:
    with pytest.raises(ValidationError):
        ApiKey(
            api_key_id="91",
            name="ci agent",
            prefix="12345",
            created_at=datetime(2026, 8, 11, 9, 10, 11),
        )


@pytest.mark.parametrize(
    "permissions",
    [
        (),
        cast(Sequence[NamespacePermission], ["VIEW_USER_PROFILE"]),
        [
            NamespacePermission.VIEW_USER_PROFILE,
            NamespacePermission.VIEW_USER_PROFILE,
        ],
    ],
)
def test_permission_validation_happens_before_transport(
    permissions: Sequence[NamespacePermission],
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(ConfigurationError),
    ):
        client.api_keys.create(
            namespace_id="42",
            name="ci agent",
            permissions=permissions,
        )

    assert request_count == 0


@pytest.mark.parametrize(
    "operation",
    ["create", "list", "get", "list_permissions", "update", "delete"],
)
def test_known_api_key_identity_cannot_call_session_only_management(
    operation: str,
) -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(500, request=request)

    with (
        Client(
            base_url="https://dicehub.test",
            api_key="test-api-key",
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(
            ConfigurationError,
            match="API-key administration requires session-cookie authentication",
        ),
    ):
        if operation == "create":
            client.api_keys.create(
                namespace_id="42",
                name="ci agent",
                permissions=[NamespacePermission.VIEW_USER_PROFILE],
            )
        elif operation == "list":
            client.api_keys.list(namespace_id="42")
        elif operation == "get":
            client.api_keys.get(namespace_id="42", api_key_id="91")
        elif operation == "list_permissions":
            client.api_keys.list_permissions(namespace_id="42")
        elif operation == "update":
            client.api_keys.update(
                namespace_id="42",
                api_key_id="91",
                name="ci agent",
            )
        else:
            client.api_keys.delete(api_key_id="91")

    assert request_count == 0
