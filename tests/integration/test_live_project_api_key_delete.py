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


def _cleanup_project(
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


def _cleanup_key(
    client: Client,
    namespace_id: str,
    api_key_id: str,
    key_name: str,
    cleanup_failures: list[str],
) -> None:
    try:
        keys = client.api_keys.list(namespace_id=namespace_id)
    except Exception:
        cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {api_key_id!r}.")
        return

    for api_key in keys:
        if api_key.api_key_id == api_key_id and api_key.name == key_name:
            try:
                client.api_keys.delete(api_key_id=api_key_id)
            except Exception:
                cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {api_key_id!r}.")
            return


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_scoped_api_key_delete_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_PROJECT_API_KEY_DELETE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_PROJECT_API_KEY_DELETE_TEST=1 to allow recursive deletion.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    sdk_target_id: str | None = None
    cli_target_id: str | None = None
    control_id: str | None = None
    sdk_key_id: str | None = None
    cli_key_id: str | None = None
    ambiguous_project_ids: set[str] = set()
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        sdk_key_name = f"dicehub-python-project-delete-sdk-{marker}"
        cli_key_name = f"dicehub-python-project-delete-cli-{marker}"
        try:
            try:
                sdk_target = session_client.projects.create(
                    name=f"dicehub-python-delete-sdk-{marker}",
                    slug=f"dh-key-delete-sdk-{marker}",
                    visibility=ProjectVisibility.PRIVATE,
                )
                sdk_target_id = sdk_target.project_id
                cli_target = session_client.projects.create(
                    name=f"dicehub-python-delete-cli-{marker}",
                    slug=f"dh-key-delete-cli-{marker}",
                    visibility=ProjectVisibility.PRIVATE,
                )
                cli_target_id = cli_target.project_id
                control = session_client.projects.create(
                    name=f"dicehub-python-delete-control-{marker}",
                    slug=f"dh-key-delete-control-{marker}",
                    visibility=ProjectVisibility.PRIVATE,
                )
                control_id = control.project_id
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Create outcome unknown; reconcile projects with marker {marker!r}.",
                    pytrace=False,
                )

            sdk_key = session_client.api_keys.create(
                namespace_id=sdk_target_id,
                name=sdk_key_name,
                permissions=[NamespacePermission.DELETE_PROJECT],
            )
            sdk_key_id = sdk_key.api_key_id
            sdk_secret = sdk_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=sdk_secret) as key_client:
                with pytest.raises(APIError):
                    key_client.projects.delete(project_id=control_id)
                try:
                    key_client.projects.delete(project_id=sdk_target_id)
                except MutationOutcomeUnknownError:
                    ambiguous_project_ids.add(sdk_target_id)
                    pytest.fail(
                        f"Delete outcome unknown; reconcile project ID {sdk_target_id!r}.",
                        pytrace=False,
                    )
            sdk_target_id = None
            sdk_key_id = None

            with (
                Client(base_url=base_url, api_key=sdk_secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()

            cli_key = session_client.api_keys.create(
                namespace_id=cli_target_id,
                name=cli_key_name,
                permissions=[NamespacePermission.DELETE_PROJECT],
            )
            cli_key_id = cli_key.api_key_id
            cli_secret = cli_key.value.get_secret_value()
            executable = Path(sys.executable).with_name("dicehub")
            result = subprocess.run(
                [
                    executable,
                    "project",
                    "delete",
                    cli_target_id,
                    "--yes",
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env={"DICEHUB_API_KEY": cli_secret, "DICEHUB_URL": base_url},
                text=True,
            )
            assert cli_secret not in result.stdout + result.stderr
            if result.returncode != 0:
                payload = json.loads(result.stdout)
                if payload["error"]["code"] == "MUTATION_OUTCOME_UNKNOWN":
                    ambiguous_project_ids.add(cli_target_id)
                pytest.fail(
                    f"CLI deletion failed for exact project ID {cli_target_id!r}.",
                    pytrace=False,
                )
            assert json.loads(result.stdout)["data"] == {"project_id": cli_target_id}
            cli_target_id = None
            cli_key_id = None

            with (
                Client(base_url=base_url, api_key=cli_secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()

            assert session_client.projects.get(project_id=control_id).project_id == control_id
        finally:
            if sdk_target_id is not None and sdk_key_id is not None:
                _cleanup_key(
                    session_client,
                    sdk_target_id,
                    sdk_key_id,
                    sdk_key_name,
                    cleanup_failures,
                )
            if cli_target_id is not None and cli_key_id is not None:
                _cleanup_key(
                    session_client,
                    cli_target_id,
                    cli_key_id,
                    cli_key_name,
                    cleanup_failures,
                )
            for project_id in (control_id, cli_target_id, sdk_target_id):
                if project_id is not None and project_id not in ambiguous_project_ids:
                    _cleanup_project(session_client, project_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
