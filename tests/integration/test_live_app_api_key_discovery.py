from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import (
    App,
    AppVisibility,
    AuthenticationError,
    Client,
    NamespacePermission,
)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_scoped_api_key_app_discovery_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_APP_API_KEY_DISCOVERY_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_APP_API_KEY_DISCOVERY_TEST=1 to allow API-key mutations.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    key_name = f"dicehub-python-app-discovery-{uuid.uuid4().hex}"
    key_id: str | None = None
    secret: str | None = None
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        candidate: App | None = None
        for project in session_client.projects.list(limit=50).projects:
            for app in session_client.apps.list(project_id=project.project_id, limit=20).apps:
                if app.visibility in {AppVisibility.INTERNAL, AppVisibility.PRIVATE} and app.route:
                    candidate = app
                    break
            if candidate is not None:
                break

        if candidate is None:
            pytest.skip("No private or internal app with a route is available for discovery.")
        candidate_route = candidate.route
        assert candidate_route is not None

        baseline_ids = {
            key.api_key_id
            for key in session_client.api_keys.list(namespace_id=candidate.project_id)
        }
        try:
            created = session_client.api_keys.create(
                namespace_id=candidate.project_id,
                name=key_name,
                permissions=[NamespacePermission.VIEW_APP_INFO],
            )
            key_id = created.api_key_id
            secret = created.value.get_secret_value()

            with Client(base_url=base_url, api_key=secret) as key_client:
                page = key_client.apps.list(project_id=candidate.project_id, limit=50)
                assert candidate.app_id in {app.app_id for app in page.apps}
                by_id = key_client.apps.get(app_id=candidate.app_id)
                by_route = key_client.apps.get_by_route(route=candidate_route)
                assert by_id.app_id == by_route.app_id == candidate.app_id

            executable = Path(sys.executable).with_name("dicehub")
            environment = {"DICEHUB_API_KEY": secret, "DICEHUB_URL": base_url}
            list_result = subprocess.run(
                [
                    executable,
                    "app",
                    "list",
                    candidate.project_id,
                    "--limit",
                    "50",
                    "--output",
                    "json",
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            assert secret not in list_result.stdout + list_result.stderr
            assert list_result.returncode == 0
            listed_ids = {app["app_id"] for app in json.loads(list_result.stdout)["data"]["apps"]}
            assert candidate.app_id in listed_ids

            get_result = subprocess.run(
                [executable, "app", "get", candidate.app_id, "--output", "json"],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            assert secret not in get_result.stdout + get_result.stderr
            assert get_result.returncode == 0
            assert json.loads(get_result.stdout)["data"]["app"]["app_id"] == candidate.app_id

            session_client.api_keys.delete(api_key_id=key_id)
            key_id = None

            with (
                Client(base_url=base_url, api_key=secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.apps.get(app_id=candidate.app_id)
        finally:
            if key_id is not None:
                try:
                    keys = session_client.api_keys.list(namespace_id=candidate.project_id)
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
