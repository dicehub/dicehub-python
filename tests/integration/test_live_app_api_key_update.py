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


def _find_template_id(client: Client) -> str | None:
    configured = os.environ.get("DICEHUB_LIVE_APP_TEMPLATE_ID")
    if configured is not None:
        return configured

    for project in client.projects.list(limit=50).projects:
        for app in client.apps.list(project_id=project.project_id, limit=50).apps:
            detail = client.apps.get(app_id=app.app_id)
            if detail.template_id is not None:
                return detail.template_id
    return None


def _delete_project(client: Client, project_id: str, failures: list[str]) -> None:
    try:
        client.projects.delete(project_id=project_id)
    except MutationOutcomeUnknownError:
        failures.append(f"Cleanup outcome unknown; reconcile project ID {project_id!r}.")
    except Exception:
        failures.append(f"Cleanup failed; reconcile project ID {project_id!r}.")


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_key_updates_app_metadata_through_sdk_and_cli() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_APP_API_KEY_UPDATE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_APP_API_KEY_UPDATE_TEST=1 to allow app and API-key mutations."
        )

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    target_project_id: str | None = None
    control_project_id: str | None = None
    key_id: str | None = None
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        template_id = _find_template_id(session_client)
        if template_id is None:
            pytest.skip(
                "No source template was found; set DICEHUB_LIVE_APP_TEMPLATE_ID explicitly."
            )

        try:
            try:
                target_project = session_client.projects.create(
                    name=f"dicehub app-update target {marker}",
                    slug=f"dh-app-update-target-{marker}",
                    description="Temporary API-key app-update target",
                    visibility=ProjectVisibility.PRIVATE,
                )
                target_project_id = target_project.project_id
                control_project = session_client.projects.create(
                    name=f"dicehub app-update control {marker}",
                    slug=f"dh-app-update-control-{marker}",
                    description="Temporary API-key app-update control",
                    visibility=ProjectVisibility.PRIVATE,
                )
                control_project_id = control_project.project_id
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Project outcome unknown; reconcile personal marker {marker!r}.",
                    pytrace=False,
                )

            try:
                target_app = session_client.apps.create(
                    project_id=target_project_id,
                    template_id=template_id,
                    name=f"Target app {marker}",
                    description="Original target description",
                )
                control_app = session_client.apps.create(
                    project_id=control_project_id,
                    template_id=template_id,
                    name=f"Control app {marker}",
                    description="Original control description",
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    "App outcome unknown; reconcile project IDs "
                    f"{target_project_id!r} and {control_project_id!r}.",
                    pytrace=False,
                )

            created_key = session_client.api_keys.create(
                namespace_id=target_project_id,
                name=f"dicehub-python-update-app-{marker}",
                permissions=[NamespacePermission.EDIT_APP_INFO],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                key_client.apps.update(
                    app_id=target_app.app_id,
                    description="Updated through the dicehub Python SDK",
                )
                with pytest.raises(APIError):
                    key_client.apps.update(
                        app_id=control_app.app_id,
                        description="must not be written",
                    )

            after_sdk = session_client.apps.get(app_id=target_app.app_id)
            assert after_sdk.name == target_app.name
            assert after_sdk.description == "Updated through the dicehub Python SDK"
            unchanged_control = session_client.apps.get(app_id=control_app.app_id)
            assert unchanged_control.description == "Original control description"

            executable = Path(sys.executable).with_name("dicehub")
            cli_name = f"CLI-updated app {marker}"
            result = subprocess.run(
                [
                    executable,
                    "app",
                    "update",
                    target_app.app_id,
                    "--name",
                    cli_name,
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env={"DICEHUB_API_KEY": secret, "DICEHUB_URL": base_url},
                text=True,
            )
            assert secret not in result.stdout + result.stderr
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["data"] == {"app_id": target_app.app_id}

            after_cli = session_client.apps.get(app_id=target_app.app_id)
            assert after_cli.name == cli_name
            assert after_cli.description == "Updated through the dicehub Python SDK"

            session_client.api_keys.delete(api_key_id=key_id)
            key_id = None
            with (
                Client(base_url=base_url, api_key=secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()
        finally:
            if key_id is not None:
                try:
                    session_client.api_keys.delete(api_key_id=key_id)
                except Exception:
                    cleanup_failures.append(f"API-key cleanup failed; reconcile ID {key_id!r}.")
            if control_project_id is not None:
                _delete_project(session_client, control_project_id, cleanup_failures)
            if target_project_id is not None:
                _delete_project(session_client, target_project_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
