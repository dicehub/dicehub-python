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
    AppVisibility,
    AuthenticationError,
    Client,
    NamespacePermission,
    Run,
)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_scoped_api_key_run_discovery_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_RUN_API_KEY_DISCOVERY_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_RUN_API_KEY_DISCOVERY_TEST=1 to allow API-key mutations.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    key_name = f"dicehub-python-run-discovery-{uuid.uuid4().hex}"
    key_id: str | None = None
    secret: str | None = None
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        candidate_project_id: str | None = None
        candidate: Run | None = None
        sibling: Run | None = None

        for project in session_client.projects.list(limit=50).projects:
            page = session_client.runs.list(
                namespace_id=project.project_id,
                include_descendants=True,
                limit=50,
            )
            private_run: Run | None = None
            for run in page.runs:
                try:
                    app = session_client.apps.get(app_id=run.namespace_id)
                except APIError:
                    continue
                if app.visibility in {AppVisibility.INTERNAL, AppVisibility.PRIVATE}:
                    private_run = run
                    break
            if private_run is None:
                continue
            if candidate is None:
                candidate_project_id = project.project_id
                candidate = private_run
            elif project.project_id != candidate_project_id:
                sibling = private_run
                break

        if candidate_project_id is None or candidate is None:
            pytest.skip("No private or internal app run is available for discovery.")

        baseline_ids = {
            key.api_key_id
            for key in session_client.api_keys.list(namespace_id=candidate_project_id)
        }
        try:
            created = session_client.api_keys.create(
                namespace_id=candidate_project_id,
                name=key_name,
                permissions=[NamespacePermission.VIEW_RUN_INFO],
            )
            key_id = created.api_key_id
            secret = created.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                page = key_client.runs.list(
                    namespace_id=candidate_project_id,
                    include_descendants=True,
                    limit=50,
                )
                assert candidate.run_id in {run.run_id for run in page.runs}
                detail = key_client.runs.get(run_id=candidate.run_id)
                status = key_client.runs.status(run_id=candidate.run_id)
                assert detail.run_id == status.run_id == candidate.run_id
                watcher = key_client.runs.watch(
                    run_id=candidate.run_id,
                    timeout_seconds=5,
                    poll_seconds=1,
                )
                watched = next(watcher)
                watcher.close()
                assert watched.run_id == candidate.run_id
                with pytest.raises(APIError):
                    key_client.apps.get(app_id=candidate.namespace_id)
                if sibling is not None:
                    with pytest.raises(APIError):
                        key_client.runs.get(run_id=sibling.run_id)

            executable = str(Path(sys.executable).with_name("dicehub"))
            environment = {"DICEHUB_API_KEY": secret, "DICEHUB_URL": base_url}
            commands = [
                (
                    "list",
                    [
                        executable,
                        "run",
                        "list",
                        candidate_project_id,
                        "--include-descendants",
                        "--limit",
                        "50",
                        "--output",
                        "json",
                    ],
                ),
                (
                    "get",
                    [executable, "run", "get", candidate.run_id, "--output", "json"],
                ),
                (
                    "status",
                    [executable, "run", "status", candidate.run_id, "--output", "json"],
                ),
            ]
            for command_name, command in commands:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    check=False,
                    env=environment,
                    text=True,
                    timeout=30,
                )
                assert secret not in result.stdout + result.stderr
                assert result.returncode == 0, result.stdout + result.stderr
                payload = json.loads(result.stdout)
                assert payload["ok"] is True
                if command_name == "list":
                    assert candidate.run_id in {run["run_id"] for run in payload["data"]["runs"]}
                elif command_name == "get":
                    assert payload["data"]["run"]["run_id"] == candidate.run_id
                else:
                    assert payload["data"]["run_status"]["run_id"] == candidate.run_id

            session_client.api_keys.delete(api_key_id=key_id)
            key_id = None

            with (
                Client(base_url=base_url, api_key=secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.runs.status(run_id=candidate.run_id)
        finally:
            if key_id is not None:
                try:
                    keys = session_client.api_keys.list(namespace_id=candidate_project_id)
                except Exception:
                    cleanup_failures.append(f"API-key cleanup failed; reconcile key ID {key_id!r}.")
                else:
                    for key in keys:
                        if (
                            key.api_key_id == key_id
                            and key.name == key_name
                            and key.api_key_id not in baseline_ids
                        ):
                            try:
                                session_client.api_keys.delete(api_key_id=key_id)
                            except Exception:
                                cleanup_failures.append(
                                    f"API-key cleanup failed; reconcile key ID {key_id!r}."
                                )
                            break
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
