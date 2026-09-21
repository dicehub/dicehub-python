from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import (
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
def test_live_project_key_creates_apps_through_sdk_and_cli() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_APP_API_KEY_CREATE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_APP_API_KEY_CREATE_TEST=1 to allow app and API-key mutations."
        )

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    project_name = f"dicehub-python-app-create-{marker}"
    project_id: str | None = None
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
                project = session_client.projects.create(
                    name=project_name,
                    slug=f"dh-app-create-{marker}",
                    description="Temporary project for API-key app creation",
                    visibility=ProjectVisibility.PRIVATE,
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Project outcome unknown; reconcile personal marker {marker!r}.",
                    pytrace=False,
                )
            project_id = project.project_id

            created_key = session_client.api_keys.create(
                namespace_id=project_id,
                name=f"dicehub-python-create-app-{marker}",
                permissions=[NamespacePermission.CREATE_APP],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                try:
                    sdk_app = key_client.apps.create(
                        project_id=project_id,
                        template_id=template_id,
                        name=f"SDK app {marker}",
                        description="Created through the dicehub Python SDK",
                    )
                except MutationOutcomeUnknownError:
                    pytest.fail(
                        f"App outcome unknown; reconcile project ID {project_id!r}.",
                        pytrace=False,
                    )
                assert sdk_app.project_id == project_id
                assert sdk_app.template_id == template_id

            executable = Path(sys.executable).with_name("dicehub")
            result = subprocess.run(
                [
                    executable,
                    "app",
                    "create",
                    project_id,
                    "--template-id",
                    template_id,
                    "--name",
                    f"CLI app {marker}",
                    "--description",
                    "Created through the dicehub CLI",
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env={"DICEHUB_API_KEY": secret, "DICEHUB_URL": base_url},
                text=True,
            )
            assert secret not in result.stdout + result.stderr
            if result.returncode != 0:
                pytest.fail(
                    f"CLI create failed; reconcile project ID {project_id!r}.",
                    pytrace=False,
                )
            try:
                cli_app_id = json.loads(result.stdout)["data"]["app"]["app_id"]
            except (KeyError, TypeError, json.JSONDecodeError):
                pytest.fail(
                    f"CLI returned no exact app ID; reconcile project ID {project_id!r}.",
                    pytrace=False,
                )
            assert isinstance(cli_app_id, str)
            assert session_client.apps.get(app_id=cli_app_id).project_id == project_id

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
            if project_id is not None:
                _delete_project(session_client, project_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
