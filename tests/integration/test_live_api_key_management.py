from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta

import pytest
from pydantic import SecretStr

from dicehub import (
    ApiKey,
    ApiKeyStatus,
    AuthenticationError,
    Client,
    CreatedApiKey,
    IdentityMode,
    MutationOutcomeUnknownError,
    NamespacePermission,
)


def _assert_timestamp(value: datetime | None) -> datetime:
    assert value is not None
    assert value.utcoffset() == timedelta(0)
    return value


def _assert_metadata(
    api_key: ApiKey,
    *,
    api_key_id: str,
    name: str,
    permissions: tuple[NamespacePermission, ...],
) -> None:
    assert api_key.api_key_id == api_key_id
    assert api_key.name == name
    assert api_key.prefix
    assert api_key.permissions == permissions
    assert api_key.status is ApiKeyStatus.ACTIVE
    created_at = _assert_timestamp(api_key.created_at)
    updated_at = _assert_timestamp(api_key.updated_at)
    assert updated_at >= created_at
    if api_key.last_used_at is not None:
        _assert_timestamp(api_key.last_used_at)


def _wait_for_last_used(
    client: Client,
    *,
    namespace_id: str,
    api_key_id: str,
) -> ApiKey:
    deadline = time.monotonic() + 5.0
    while True:
        api_key = client.api_keys.get(
            namespace_id=namespace_id,
            api_key_id=api_key_id,
        )
        assert api_key is not None
        if api_key.last_used_at is not None:
            return api_key
        if time.monotonic() >= deadline:
            pytest.fail("The API-key last-used timestamp was not recorded.", pytrace=False)
        time.sleep(0.1)


def _recover_created_id(
    client: Client,
    *,
    namespace_id: str,
    name: str,
    baseline_ids: set[str],
) -> str | None:
    try:
        matches = [
            api_key.api_key_id
            for api_key in client.api_keys.list(namespace_id=namespace_id)
            if api_key.name == name and api_key.api_key_id not in baseline_ids
        ]
    except Exception:
        return None
    return matches[0] if len(matches) == 1 else None


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_session_managed_api_key_administration() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_MANAGED_KEY_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_MANAGED_KEY_TEST=1 to allow API-key mutations.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = f"dicehub-python-admin-{uuid.uuid4().hex}"
    renamed = f"{marker}-renamed"
    api_key_id: str | None = None
    delete_outcome_unknown = False
    cleanup_failure: str | None = None

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        assert session_client.auth.context().identity_mode is IdentityMode.SESSION
        namespace_id = session_client.users.me().user_id
        baseline_ids = {
            api_key.api_key_id
            for api_key in session_client.api_keys.list(namespace_id=namespace_id)
        }
        catalog = session_client.api_keys.list_permissions(namespace_id=namespace_id)
        assert catalog
        assert NamespacePermission.NONE not in catalog
        assert len(catalog) == len(set(catalog))
        if len(catalog) < 2:
            pytest.skip("The namespace must expose at least two assignable API-key permissions.")
        initial_permissions = (catalog[0],)
        replacement_permissions = (catalog[-1],)

        try:
            try:
                created = session_client.api_keys.create(
                    namespace_id=namespace_id,
                    name=marker,
                    permissions=initial_permissions,
                )
            except MutationOutcomeUnknownError:
                api_key_id = _recover_created_id(
                    session_client,
                    namespace_id=namespace_id,
                    name=marker,
                    baseline_ids=baseline_ids,
                )
                pytest.fail(
                    f"Create outcome unknown; reconcile API-key name {marker!r}.",
                    pytrace=False,
                )

            assert isinstance(created, CreatedApiKey)
            assert isinstance(created.value, SecretStr)
            api_key_id = created.api_key_id
            _assert_metadata(
                created,
                api_key_id=api_key_id,
                name=marker,
                permissions=initial_permissions,
            )
            assert created.last_used_at is None
            if not created.value.get_secret_value().startswith(created.prefix):
                pytest.fail("The API-key prefix does not match its creation secret.", pytrace=False)
            serialized = repr(created) + created.model_dump_json()
            if created.value.get_secret_value() in serialized:
                pytest.fail("The created API-key model exposed its secret.", pytrace=False)

            fetched = session_client.api_keys.get(
                namespace_id=namespace_id,
                api_key_id=api_key_id,
            )
            assert fetched is not None
            _assert_metadata(
                fetched,
                api_key_id=api_key_id,
                name=marker,
                permissions=initial_permissions,
            )
            assert not hasattr(fetched, "value")
            listed = session_client.api_keys.list(namespace_id=namespace_id)
            listed_matches = [key for key in listed if key.api_key_id == api_key_id]
            assert listed_matches == [fetched]
            assert all(not hasattr(key, "value") for key in listed)

            with Client(
                base_url=base_url,
                api_key=created.value.get_secret_value(),
            ) as api_key_client:
                assert api_key_client.auth.context().identity_mode is IdentityMode.API_KEY

            used = _wait_for_last_used(
                session_client,
                namespace_id=namespace_id,
                api_key_id=api_key_id,
            )
            _assert_timestamp(used.last_used_at)

            try:
                renamed_key = session_client.api_keys.update(
                    namespace_id=namespace_id,
                    api_key_id=api_key_id,
                    name=renamed,
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Rename outcome unknown; reconcile API-key ID {api_key_id!r}.",
                    pytrace=False,
                )
            _assert_metadata(
                renamed_key,
                api_key_id=api_key_id,
                name=renamed,
                permissions=initial_permissions,
            )
            assert renamed_key.prefix == created.prefix
            assert renamed_key.created_at == created.created_at
            assert renamed_key.last_used_at == used.last_used_at
            assert not hasattr(renamed_key, "value")

            try:
                replaced = session_client.api_keys.update(
                    namespace_id=namespace_id,
                    api_key_id=api_key_id,
                    name=renamed,
                    permissions=replacement_permissions,
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Permission update outcome unknown; reconcile API-key ID {api_key_id!r}.",
                    pytrace=False,
                )
            _assert_metadata(
                replaced,
                api_key_id=api_key_id,
                name=renamed,
                permissions=replacement_permissions,
            )
            assert replaced.prefix == created.prefix
            assert replaced.created_at == created.created_at
            assert replaced.last_used_at == used.last_used_at
            assert not hasattr(replaced, "value")
            final = session_client.api_keys.get(
                namespace_id=namespace_id,
                api_key_id=api_key_id,
            )
            assert final == replaced

            try:
                session_client.api_keys.delete(api_key_id=api_key_id)
            except MutationOutcomeUnknownError:
                delete_outcome_unknown = True
                pytest.fail(
                    f"Revoke outcome unknown; reconcile API-key ID {api_key_id!r}.",
                    pytrace=False,
                )
            else:
                api_key_id = None

            assert (
                session_client.api_keys.get(
                    namespace_id=namespace_id,
                    api_key_id=created.api_key_id,
                )
                is None
            )
            with (
                Client(
                    base_url=base_url,
                    api_key=created.value.get_secret_value(),
                ) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()
        finally:
            if api_key_id is not None and not delete_outcome_unknown:
                try:
                    session_client.api_keys.delete(api_key_id=api_key_id)
                except MutationOutcomeUnknownError:
                    cleanup_failure = (
                        f"Cleanup outcome unknown; reconcile API-key ID {api_key_id!r}."
                    )
                except Exception:
                    cleanup_failure = f"Cleanup failed; reconcile API-key ID {api_key_id!r}."
            if cleanup_failure is not None:
                pytest.fail(cleanup_failure, pytrace=False)
