from __future__ import annotations

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
    AuthenticationError,
    Client,
    ConfigContentArea,
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


def _delete_project(client: Client, project_id: str, failures: list[str]) -> None:
    try:
        client.projects.delete(project_id=project_id)
    except MutationOutcomeUnknownError:
        failures.append(f"Cleanup outcome unknown; reconcile project ID {project_id!r}.")
    except Exception:
        failures.append(f"Cleanup failed; reconcile project ID {project_id!r}.")


def _run_cli(executable: Path, secret: str, base_url: str, *arguments: str) -> dict[str, object]:
    result = subprocess.run(
        [executable, *arguments, "--output", "json"],
        capture_output=True,
        check=False,
        env={"DICEHUB_API_KEY": secret, "DICEHUB_URL": base_url},
        text=True,
    )
    assert secret not in result.stdout + result.stderr
    if result.returncode != 0:
        pytest.fail(f"CLI command {arguments[:3]!r} failed.", pytrace=False)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"CLI command {arguments[:3]!r} returned invalid JSON.", pytrace=False)
    assert payload["ok"] is True
    data = payload["data"]
    assert isinstance(data, dict)
    return data


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_key_edits_config_metadata_text_and_files(tmp_path: Path) -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_CONFIG_API_KEY_EDIT_TEST") != "1":
        pytest.skip(
            "Set DICEHUB_LIVE_CONFIG_API_KEY_EDIT_TEST=1 to allow config and API-key mutations."
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
                    name=f"dicehub config-edit target {marker}",
                    slug=f"dh-config-edit-target-{marker}",
                    description="Temporary API-key config-edit target",
                    visibility=ProjectVisibility.PRIVATE,
                )
                target_project_id = target_project.project_id
                control_project = session_client.projects.create(
                    name=f"dicehub config-edit control {marker}",
                    slug=f"dh-config-edit-control-{marker}",
                    description="Temporary API-key config-edit control",
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
                    name=f"Target config-edit app {marker}",
                )
                control_app = session_client.apps.create(
                    project_id=control_project_id,
                    template_id=template_id,
                    name=f"Control config-edit app {marker}",
                )
                target_config = session_client.configs.create(
                    app_id=target_app.app_id,
                    name=f"Target editable config {marker}",
                )
                control_config = session_client.configs.create(
                    app_id=control_app.app_id,
                    name=f"Control config {marker}",
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    "Setup outcome unknown; reconcile project IDs "
                    f"{target_project_id!r} and {control_project_id!r}.",
                    pytrace=False,
                )

            created_key = session_client.api_keys.create(
                namespace_id=target_project_id,
                name=f"dicehub-python-edit-config-{marker}",
                permissions=[
                    NamespacePermission.EDIT_CONFIG_INFO,
                    NamespacePermission.VIEW_CONFIG_CONTENT,
                    NamespacePermission.EDIT_CONFIG_CONTENT,
                ],
            )
            key_id = created_key.api_key_id
            secret = created_key.value.get_secret_value()

            sdk_text_path = f"sdk/{marker}.yaml"
            sdk_file_path = f"sdk/{marker}.bin"
            sdk_text = "iterations: 200\n"
            sdk_file = b"dicehub-sdk-config-file\x00\xff"
            with Client(base_url=base_url, api_key=secret) as key_client:
                key_client.configs.update(
                    config_id=target_config.config_id,
                    description="Updated through the dicehub Python SDK",
                )
                key_client.configs.set_text(
                    config_id=target_config.config_id,
                    path=sdk_text_path,
                    content=sdk_text,
                )
                assert (
                    key_client.configs.get_text(
                        config_id=target_config.config_id,
                        path=sdk_text_path,
                    )
                    == sdk_text
                )
                key_client.configs.upload_file(
                    config_id=target_config.config_id,
                    path=sdk_file_path,
                    source=io.BytesIO(sdk_file),
                )
                downloaded = io.BytesIO()
                assert key_client.configs.download_file(
                    config_id=target_config.config_id,
                    path=sdk_file_path,
                    destination=downloaded,
                ) == len(sdk_file)
                assert downloaded.getvalue() == sdk_file

                text_paths = {
                    entry.path
                    for entry in key_client.configs.list_content(
                        config_id=target_config.config_id,
                        area=ConfigContentArea.TEXTS,
                        path="sdk",
                        recursive=True,
                        limit=50,
                    ).entries
                }
                file_paths = {
                    entry.path
                    for entry in key_client.configs.list_content(
                        config_id=target_config.config_id,
                        area=ConfigContentArea.FILES,
                        path="sdk",
                        recursive=True,
                        limit=50,
                    ).entries
                }
                assert sdk_text_path in text_paths
                assert sdk_file_path in file_paths

                with pytest.raises(APIError):
                    key_client.configs.update(
                        config_id=control_config.config_id,
                        description="Denied sibling metadata update",
                    )
                with pytest.raises(APIError):
                    key_client.configs.list_content(
                        config_id=control_config.config_id,
                        area=ConfigContentArea.TEXTS,
                    )
                with pytest.raises(APIError):
                    key_client.configs.set_text(
                        config_id=control_config.config_id,
                        path=f"denied/{marker}.yaml",
                        content="denied\n",
                    )

            assert (
                session_client.configs.get(config_id=target_config.config_id).description
                == "Updated through the dicehub Python SDK"
            )

            executable = Path(sys.executable).with_name("dicehub")
            cli_text_path = f"cli/{marker}.yaml"
            cli_file_path = f"cli/{marker}.bin"
            text_source = tmp_path / "config-text.yaml"
            file_source = tmp_path / "config-file.bin"
            file_destination = tmp_path / "downloaded-config-file.bin"
            text_source.write_text("iterations: 300\n", encoding="utf-8")
            file_source.write_bytes(b"dicehub-cli-config-file\x00\xff")

            _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "update",
                target_config.config_id,
                "--description",
                "Updated through the dicehub CLI",
            )
            _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "set-text",
                target_config.config_id,
                cli_text_path,
                str(text_source),
            )
            text_data = _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "get-text",
                target_config.config_id,
                cli_text_path,
            )
            assert text_data["content"] == "iterations: 300\n"
            _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "upload",
                target_config.config_id,
                cli_file_path,
                str(file_source),
            )
            download_data = _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "download",
                target_config.config_id,
                cli_file_path,
                str(file_destination),
            )
            assert download_data["bytes"] == file_source.stat().st_size
            assert file_destination.read_bytes() == file_source.read_bytes()

            _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "delete",
                target_config.config_id,
                cli_text_path,
                "--area",
                "texts",
                "--yes",
            )
            _run_cli(
                executable,
                secret,
                base_url,
                "config",
                "content",
                "delete",
                target_config.config_id,
                cli_file_path,
                "--area",
                "files",
                "--yes",
            )

            with Client(base_url=base_url, api_key=secret) as key_client:
                key_client.configs.delete_content(
                    config_id=target_config.config_id,
                    area=ConfigContentArea.TEXTS,
                    path=sdk_text_path,
                )
                key_client.configs.delete_content(
                    config_id=target_config.config_id,
                    area=ConfigContentArea.FILES,
                    path=sdk_file_path,
                )
                with pytest.raises(APIError):
                    key_client.configs.get_text(
                        config_id=target_config.config_id,
                        path=sdk_text_path,
                    )

            assert (
                session_client.configs.get(config_id=target_config.config_id).description
                == "Updated through the dicehub CLI"
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
