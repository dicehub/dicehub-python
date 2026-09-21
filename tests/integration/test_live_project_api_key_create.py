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


def _delete_project(client: Client, project_id: str, cleanup_failures: list[str]) -> None:
    try:
        client.projects.delete(project_id=project_id)
    except MutationOutcomeUnknownError:
        cleanup_failures.append(f"Cleanup outcome unknown; reconcile project ID {project_id!r}.")
    except Exception:
        cleanup_failures.append(f"Cleanup failed; reconcile project ID {project_id!r}.")


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_personal_api_key_project_create_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_PROJECT_API_KEY_CREATE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_PROJECT_API_KEY_CREATE_TEST=1 to allow project and API-key mutations."
        )

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    sdk_name = f"dicehub-python-key-create-sdk-{marker}"
    cli_name = f"dicehub-python-key-create-cli-{marker}"
    denied_name = f"dicehub-python-key-create-denied-{marker}"
    key_name = f"dicehub-python-project-create-{marker}"
    key_id: str | None = None
    project_ids: list[str] = []
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        namespace_id = session_client.users.me().user_id
        baseline_key_ids = {
            api_key.api_key_id
            for api_key in session_client.api_keys.list(namespace_id=namespace_id)
        }
        try:
            created_key = session_client.api_keys.create(
                namespace_id=namespace_id,
                name=key_name,
                permissions=[
                    NamespacePermission.CREATE_USER_PROJECT,
                    NamespacePermission.VIEW_PROJECT_INFO,
                ],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                try:
                    sdk_project = key_client.projects.create(
                        name=sdk_name,
                        slug=f"dh-key-create-sdk-{marker}",
                        description="Created through the dicehub Python SDK",
                        visibility=ProjectVisibility.PRIVATE,
                    )
                except MutationOutcomeUnknownError:
                    pytest.fail(
                        f"Create outcome unknown; reconcile personal project marker {marker!r}.",
                        pytrace=False,
                    )
                project_ids.append(sdk_project.project_id)
                assert (
                    key_client.projects.get(project_id=sdk_project.project_id).description
                    == "Created through the dicehub Python SDK"
                )

                try:
                    unexpected = key_client.projects.create(
                        name=denied_name,
                        slug=f"dh-key-create-denied-{marker}",
                        group_id=namespace_id,
                        visibility=ProjectVisibility.PRIVATE,
                    )
                except APIError:
                    pass
                except MutationOutcomeUnknownError:
                    pytest.fail(
                        f"Denied-create outcome unknown; reconcile marker {marker!r}.",
                        pytrace=False,
                    )
                else:
                    project_ids.append(unexpected.project_id)
                    pytest.fail(
                        "A personal-scoped key created a project through groupId.",
                        pytrace=False,
                    )

            executable = Path(sys.executable).with_name("dicehub")
            result = subprocess.run(
                [
                    executable,
                    "project",
                    "create",
                    "--name",
                    cli_name,
                    "--slug",
                    f"dh-key-create-cli-{marker}",
                    "--description",
                    "Created through the dicehub CLI",
                    "--visibility",
                    "private",
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
                    f"CLI create failed; reconcile personal project marker {marker!r}.",
                    pytrace=False,
                )
            try:
                cli_project_id = json.loads(result.stdout)["data"]["project"]["project_id"]
            except (KeyError, TypeError, json.JSONDecodeError):
                pytest.fail(
                    f"CLI create returned no exact ID; reconcile personal marker {marker!r}.",
                    pytrace=False,
                )
            assert isinstance(cli_project_id, str)
            project_ids.append(cli_project_id)
            assert (
                session_client.projects.get(project_id=cli_project_id).description
                == "Created through the dicehub CLI"
            )

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
                    cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {key_id!r}.")
            else:
                try:
                    remaining_keys = session_client.api_keys.list(namespace_id=namespace_id)
                except Exception:
                    remaining_keys = ()
                for api_key in remaining_keys:
                    if api_key.name == key_name and api_key.api_key_id not in baseline_key_ids:
                        try:
                            session_client.api_keys.delete(api_key_id=api_key.api_key_id)
                        except Exception:
                            cleanup_failures.append(
                                f"API-key cleanup failed; reconcile key ID {api_key.api_key_id!r}."
                            )
            for project_id in reversed(project_ids):
                _delete_project(session_client, project_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
