from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import (
    APIError,
    AuthenticationError,
    Client,
    MutationOutcomeUnknownError,
    NamespacePermission,
    ProjectVisibility,
)


def _delete_project(
    client: Client,
    project_id: str,
    cleanup_failures: list[str],
) -> None:
    try:
        client.projects.delete(project_id=project_id)
    except MutationOutcomeUnknownError:
        cleanup_failures.append(f"Cleanup outcome unknown; reconcile project ID {project_id!r}.")
    except Exception:
        cleanup_failures.append(f"Cleanup failed; reconcile project ID {project_id!r}.")


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_scoped_api_key_update_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_PROJECT_API_KEY_UPDATE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_PROJECT_API_KEY_UPDATE_TEST=1 to allow project and API-key mutations."
        )

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    target_name = f"dicehub-python-key-target-{marker}"
    control_name = f"dicehub-python-key-control-{marker}"
    key_name = f"dicehub-python-project-update-{marker}"
    target_id: str | None = None
    control_id: str | None = None
    key_id: str | None = None
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        try:
            try:
                target = session_client.projects.create(
                    name=target_name,
                    slug=f"dh-key-target-{marker}",
                    description="Project-scoped API-key target",
                    visibility=ProjectVisibility.PRIVATE,
                )
                target_id = target.project_id
                control = session_client.projects.create(
                    name=control_name,
                    slug=f"dh-key-control-{marker}",
                    description="Project-scoped API-key control",
                    visibility=ProjectVisibility.PRIVATE,
                )
                control_id = control.project_id
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Create outcome unknown; reconcile projects with marker {marker!r}.",
                    pytrace=False,
                )

            created_key = session_client.api_keys.create(
                namespace_id=target_id,
                name=key_name,
                permissions=[
                    NamespacePermission.VIEW_PROJECT_INFO,
                    NamespacePermission.EDIT_PROJECT_INFO,
                ],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                key_client.projects.update(
                    project_id=target_id,
                    description="Updated through the dicehub Python SDK",
                )
                updated = key_client.projects.get(project_id=target_id)
                assert updated.description == "Updated through the dicehub Python SDK"

                with pytest.raises(APIError):
                    key_client.projects.update(
                        project_id=control_id,
                        description="must not be written",
                    )

            unchanged_control = session_client.projects.get(project_id=control_id)
            assert unchanged_control.description == "Project-scoped API-key control"

            executable = Path(sys.executable).with_name("dicehub")
            environment = {
                "DICEHUB_API_KEY": secret,
                "DICEHUB_URL": base_url,
            }
            result = subprocess.run(
                [
                    executable,
                    "project",
                    "update",
                    target_id,
                    "--description",
                    "Updated through the dicehub CLI",
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            assert secret not in result.stdout + result.stderr
            assert result.returncode == 0
            assert json.loads(result.stdout)["data"] == {"project_id": target_id}
            assert (
                session_client.projects.get(project_id=target_id).description
                == "Updated through the dicehub CLI"
            )

            session_client.api_keys.delete(api_key_id=key_id)
            key_id = None

            with (
                Client(base_url=base_url, api_key=secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()

            revoked_result = subprocess.run(
                [executable, "auth", "status", "--output", "json"],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            assert secret not in revoked_result.stdout + revoked_result.stderr
            assert revoked_result.returncode == 3
            assert json.loads(revoked_result.stdout)["error"]["code"] == "AUTH_FAILED"
        finally:
            if target_id is not None and key_id is not None:
                try:
                    api_keys = session_client.api_keys.list(namespace_id=target_id)
                except Exception:
                    cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {key_id!r}.")
                else:
                    for api_key in api_keys:
                        if api_key.api_key_id == key_id and api_key.name == key_name:
                            try:
                                session_client.api_keys.delete(api_key_id=key_id)
                            except Exception:
                                cleanup_failures.append(
                                    f"API-key cleanup failed; reconcile key ID {key_id!r}."
                                )
                            break
            if control_id is not None:
                _delete_project(session_client, control_id, cleanup_failures)
            if target_id is not None:
                _delete_project(session_client, target_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
