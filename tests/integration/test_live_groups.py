from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import (
    APIError,
    Client,
    GroupVisibility,
    MembershipVisibility,
    MutationOutcomeUnknownError,
    NamespacePermission,
)


def _delete_group_after_reconcile(
    client: Client,
    *,
    group_id: str,
    label: str,
    cleanup_failures: list[str],
) -> None:
    try:
        client.groups.get(group_id=group_id)
    except APIError:
        return
    except Exception:
        cleanup_failures.append(f"{label} lookup failed; reconcile group ID {group_id!r}.")
        return
    try:
        client.groups.delete(group_id=group_id)
    except Exception:
        cleanup_failures.append(f"{label} cleanup failed; reconcile group ID {group_id!r}.")


def _client(base_url: str) -> Client:
    api_key = os.environ.get("DICEHUB_API_KEY")
    if api_key is not None:
        return Client(base_url=base_url, api_key=api_key)

    session_cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if session_cookie is not None:
        return Client(base_url=base_url, session_cookie=session_cookie)

    pytest.skip("DICEHUB_API_KEY or DICEHUB_SESSION_COOKIE is not set.")


@pytest.mark.integration
@pytest.mark.live
def test_live_group_discovery() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live requests.")

    group_id = os.environ.get("DICEHUB_LIVE_GROUP_ID")
    if group_id is None:
        pytest.skip("Set DICEHUB_LIVE_GROUP_ID to one visible immutable group ID.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    with _client(base_url) as client:
        by_id = client.groups.get(group_id=group_id)
        by_route = client.groups.get_by_route(route=by_id.route)
        page = client.groups.list(search_filter=by_id.name, limit=50)
        matches = [group for group in page.groups if group.group_id == group_id]

    assert len(matches) == 1
    assert matches[0].group_id == by_id.group_id == by_route.group_id
    assert matches[0].route == by_id.route == by_route.route


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_group_api_key_update_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live requests.")
    if os.environ.get("DICEHUB_LIVE_GROUP_API_KEY_UPDATE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_GROUP_API_KEY_UPDATE_TEST=1 to allow group mutations.")

    api_key = os.environ.get("DICEHUB_API_KEY")
    if api_key is None:
        pytest.skip("DICEHUB_API_KEY is not set.")
    group_id = os.environ.get("DICEHUB_LIVE_GROUP_ID")
    if group_id is None:
        pytest.skip("Set DICEHUB_LIVE_GROUP_ID to one editable immutable group ID.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex[:8]
    sdk_name = f"dicehub Python SDK group edit {marker}"
    cli_name = f"dicehub CLI group edit {marker}"
    cleanup_failure: str | None = None

    with Client(base_url=base_url, api_key=api_key) as client:
        original_name = client.groups.get(group_id=group_id).name
        try:
            client.groups.update(group_id=group_id, name=sdk_name)
            assert client.groups.get(group_id=group_id).name == sdk_name

            executable = Path(sys.executable).with_name("dicehub")
            result = subprocess.run(
                [
                    executable,
                    "group",
                    "update",
                    group_id,
                    "--name",
                    cli_name,
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env={"DICEHUB_API_KEY": api_key, "DICEHUB_URL": base_url},
                text=True,
            )
            assert api_key not in result.stdout + result.stderr
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["data"] == {"group_id": group_id}
            assert client.groups.get(group_id=group_id).name == cli_name
        finally:
            try:
                current_name = client.groups.get(group_id=group_id).name
                if current_name != original_name:
                    client.groups.update(group_id=group_id, name=original_name)
                if client.groups.get(group_id=group_id).name != original_name:
                    cleanup_failure = f"Restore failed; reconcile group ID {group_id!r}."
            except MutationOutcomeUnknownError:
                cleanup_failure = f"Restore outcome unknown; reconcile group ID {group_id!r}."
            except Exception:
                cleanup_failure = f"Restore failed; reconcile group ID {group_id!r}."

    if cleanup_failure is not None:
        pytest.fail(cleanup_failure, pytrace=False)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_group_managed_key_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to enable live requests.")
    if os.environ.get("DICEHUB_LIVE_GROUP_MANAGEMENT_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_GROUP_MANAGEMENT_TEST=1 to allow group and API-key mutations."
        )

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    parent_name = f"dicehub Python group lifecycle {marker}"
    subgroup_name = f"dicehub Python subgroup lifecycle {marker}"
    key_name = f"dicehub-python-group-lifecycle-{marker}"
    parent_id: str | None = None
    subgroup_id: str | None = None
    api_key_id: str | None = None
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        user_id = session_client.users.me().user_id
        try:
            try:
                parent = session_client.groups.create(
                    name=parent_name,
                    slug=f"dh-group-{marker}",
                    description="Temporary SDK group lifecycle parent",
                    visibility=GroupVisibility.PRIVATE,
                )
            except MutationOutcomeUnknownError:
                matches = [
                    item
                    for item in session_client.groups.list(
                        search_filter=parent_name,
                        limit=50,
                    ).groups
                    if item.name == parent_name and item.parent_id is None
                ]
                if len(matches) == 1:
                    parent_id = matches[0].group_id
                pytest.fail(
                    f"Parent create outcome unknown; reconcile marker {marker!r}.",
                    pytrace=False,
                )
            parent_id = parent.group_id

            required_permissions = (
                NamespacePermission.VIEW_GROUP_INFO,
                NamespacePermission.CREATE_SUBGROUP,
                NamespacePermission.EDIT_GROUP_INFO,
                NamespacePermission.DELETE_GROUP,
                NamespacePermission.VIEW_PUBLIC_GROUP_MEMBERS,
                NamespacePermission.VIEW_PRIVATE_GROUP_MEMBERS,
                NamespacePermission.MANAGE_GROUP_MEMBERS,
            )
            catalog = session_client.api_keys.list_permissions(namespace_id=parent_id)
            assert set(required_permissions) <= set(catalog)
            created_key = session_client.api_keys.create(
                namespace_id=parent_id,
                name=key_name,
                permissions=required_permissions,
            )
            api_key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                try:
                    subgroup = key_client.groups.create(
                        parent_id=parent_id,
                        name=subgroup_name,
                        slug=f"dh-subgroup-{marker}",
                        description="Temporary SDK managed-key subgroup",
                        visibility=GroupVisibility.PRIVATE,
                    )
                except MutationOutcomeUnknownError:
                    matches = [
                        item
                        for item in session_client.groups.list(
                            parent_id=parent_id,
                            search_filter=subgroup_name,
                            limit=50,
                        ).groups
                        if item.name == subgroup_name
                    ]
                    if len(matches) == 1:
                        subgroup_id = matches[0].group_id
                    pytest.fail(
                        f"Subgroup create outcome unknown; reconcile marker {marker!r}.",
                        pytrace=False,
                    )
                subgroup_id = subgroup.group_id
                assert subgroup.parent_id == parent_id

                avatar = io.BytesIO(
                    base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
                        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
                    )
                )
                key_client.groups.set_avatar(group_id=subgroup_id, source=avatar)
                key_client.groups.clear_avatar(group_id=subgroup_id)

                roles = key_client.groups.list_roles(group_id=subgroup_id)
                role = next(
                    (item for item in roles if (item.name or "").upper() == "MEMBER"),
                    None,
                )
                if role is None:
                    role = next(
                        (item for item in roles if (item.name or "").upper() != "OWNER"),
                        None,
                    )
                if role is None:
                    pytest.fail("No non-owner group role is available.", pytrace=False)

                key_client.groups.list_team_members(group_id=subgroup_id, limit=50)
                key_client.groups.list_user_members(group_id=subgroup_id, limit=50)
                key_client.groups.add_member(
                    group_id=subgroup_id,
                    member_id=user_id,
                    role_id=role.role_id,
                    visibility=MembershipVisibility.PRIVATE,
                )
                direct = key_client.groups.list_user_members(
                    group_id=subgroup_id,
                    include_inherited=False,
                    limit=50,
                )
                assert any(
                    item.member_id == user_id and not item.inherited for item in direct.memberships
                )

                key_client.groups.update_member(
                    group_id=subgroup_id,
                    member_id=user_id,
                    visibility=MembershipVisibility.PUBLIC,
                )
                direct = key_client.groups.list_user_members(
                    group_id=subgroup_id,
                    include_inherited=False,
                    limit=50,
                )
                assert any(
                    item.member_id == user_id and item.visibility is MembershipVisibility.PUBLIC
                    for item in direct.memberships
                )

                key_client.groups.remove_member(group_id=subgroup_id, member_id=user_id)
                direct = key_client.groups.list_user_members(
                    group_id=subgroup_id,
                    include_inherited=False,
                    limit=50,
                )
                assert all(item.member_id != user_id for item in direct.memberships)

                key_client.groups.delete(group_id=subgroup_id)
                subgroup_id = None
        finally:
            if api_key_id is not None:
                try:
                    session_client.api_keys.delete(api_key_id=api_key_id)
                except Exception:
                    cleanup_failures.append(
                        f"API-key cleanup failed; reconcile key ID {api_key_id!r}."
                    )
            if subgroup_id is not None:
                _delete_group_after_reconcile(
                    session_client,
                    group_id=subgroup_id,
                    label="Subgroup",
                    cleanup_failures=cleanup_failures,
                )
            if parent_id is not None:
                _delete_group_after_reconcile(
                    session_client,
                    group_id=parent_id,
                    label="Parent",
                    cleanup_failures=cleanup_failures,
                )

    if cleanup_failures:
        pytest.fail(" ".join(cleanup_failures), pytrace=False)
