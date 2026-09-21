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
            template_id = client.apps.get(app_id=app.app_id).template_id
            if template_id is not None:
                return template_id
    return None


def _default_config_id(client: Client, app_id: str) -> str:
    for config in client.configs.list(app_id=app_id, limit=50).configs:
        if config.is_default:
            return config.config_id
    pytest.fail(f"No default config found for temporary app ID {app_id!r}.", pytrace=False)


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
def test_live_project_key_creates_configs_through_sdk_and_cli() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_CONFIG_API_KEY_CREATE_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_CONFIG_API_KEY_CREATE_TEST=1 to allow config and API-key mutations."
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
                    name=f"dicehub config-create target {marker}",
                    slug=f"dh-config-create-target-{marker}",
                    description="Temporary API-key config-create target",
                    visibility=ProjectVisibility.PRIVATE,
                )
                target_project_id = target_project.project_id
                control_project = session_client.projects.create(
                    name=f"dicehub config-create control {marker}",
                    slug=f"dh-config-create-control-{marker}",
                    description="Temporary API-key config-create control",
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
                    name=f"Target config app {marker}",
                )
                control_app = session_client.apps.create(
                    project_id=control_project_id,
                    template_id=template_id,
                    name=f"Control config app {marker}",
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    "App outcome unknown; reconcile project IDs "
                    f"{target_project_id!r} and {control_project_id!r}.",
                    pytrace=False,
                )

            target_count = session_client.configs.list(app_id=target_app.app_id, limit=50).count
            control_page = session_client.configs.list(app_id=control_app.app_id, limit=50)
            control_count = control_page.count
            control_source_id = _default_config_id(session_client, control_app.app_id)

            created_key = session_client.api_keys.create(
                namespace_id=target_project_id,
                name=f"dicehub-python-create-config-{marker}",
                permissions=[NamespacePermission.CREATE_CONFIG],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                try:
                    sdk_config = key_client.configs.create(
                        app_id=target_app.app_id,
                        name=f"SDK config {marker}",
                        description="Created through the dicehub Python SDK",
                    )
                except MutationOutcomeUnknownError:
                    pytest.fail(
                        f"Config outcome unknown; reconcile app ID {target_app.app_id!r}.",
                        pytrace=False,
                    )
                assert sdk_config.app_id == target_app.app_id
                assert sdk_config.is_default is False

                with pytest.raises(APIError):
                    key_client.configs.create(
                        app_id=control_app.app_id,
                        name=f"Denied control config {marker}",
                    )
                with pytest.raises(APIError):
                    key_client.configs.create(
                        app_id=target_app.app_id,
                        source_config_id=control_source_id,
                        name=f"Denied cross-app clone {marker}",
                    )

            executable = Path(sys.executable).with_name("dicehub")
            cli_name = f"CLI config {marker}"
            result = subprocess.run(
                [
                    executable,
                    "config",
                    "create",
                    target_app.app_id,
                    "--source-config-id",
                    sdk_config.config_id,
                    "--name",
                    cli_name,
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
                    f"CLI create failed; reconcile app ID {target_app.app_id!r}.",
                    pytrace=False,
                )
            try:
                cli_config = json.loads(result.stdout)["data"]["config"]
            except (KeyError, TypeError, json.JSONDecodeError):
                pytest.fail(
                    f"CLI returned no exact config ID; reconcile app ID {target_app.app_id!r}.",
                    pytrace=False,
                )
            assert cli_config["app_id"] == target_app.app_id
            assert cli_config["name"] == cli_name

            target_after = session_client.configs.list(app_id=target_app.app_id, limit=50)
            assert target_after.count == target_count + 2
            assert {sdk_config.config_id, cli_config["config_id"]} <= {
                config.config_id for config in target_after.configs
            }
            assert (
                session_client.configs.list(app_id=control_app.app_id, limit=50).count
                == control_count
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
                    cleanup_failures.append(f"API-key cleanup failed; reconcile ID {key_id!r}.")
            if control_project_id is not None:
                _delete_project(session_client, control_project_id, cleanup_failures)
            if target_project_id is not None:
                _delete_project(session_client, target_project_id, cleanup_failures)
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
