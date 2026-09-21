from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from dicehub import (
    ApiKey,
    AuthenticationError,
    Client,
    IdentityMode,
    MutationOutcomeUnknownError,
    NamespacePermission,
    ProjectPage,
    ProjectVisibility,
)


@pytest.mark.integration
@pytest.mark.live
def test_live_whoami() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    with Client(base_url=base_url, session_cookie=cookie) as client:
        user = client.users.me()

    assert user.user_id
    assert user.username


@pytest.mark.integration
@pytest.mark.live
def test_live_cli_whoami() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if "DICEHUB_SESSION_COOKIE" not in os.environ:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    executable = Path(sys.executable).with_name("dicehub")
    result = subprocess.run(
        [executable, "auth", "whoami", "--output", "json"],
        capture_output=True,
        check=False,
        env={
            "DICEHUB_SESSION_COOKIE": os.environ["DICEHUB_SESSION_COOKIE"],
            "DICEHUB_URL": os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080"),
        },
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "dicehub.cli/v1"
    assert payload["ok"] is True
    assert set(payload["data"]) == {"user_id", "username"}


@pytest.mark.integration
@pytest.mark.live
def test_live_api_key_auth_context() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")

    api_key = os.environ.get("DICEHUB_API_KEY")
    if api_key is None:
        pytest.skip("DICEHUB_API_KEY is not set.")

    base_url = os.environ.get("DICEHUB_URL")
    if base_url is None:
        pytest.skip("DICEHUB_URL is not set.")
    with Client(base_url=base_url, api_key=api_key) as client:
        context = client.auth.context()

    assert context.identity_mode is IdentityMode.API_KEY


@pytest.mark.integration
@pytest.mark.live
def test_live_api_key_project_detail() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")

    api_key = os.environ.get("DICEHUB_API_KEY")
    project_id = os.environ.get("DICEHUB_LIVE_PROJECT_ID")
    base_url = os.environ.get("DICEHUB_URL")
    if api_key is None:
        pytest.skip("DICEHUB_API_KEY is not set.")
    if project_id is None:
        pytest.skip("DICEHUB_LIVE_PROJECT_ID is not set.")
    if base_url is None:
        pytest.skip("DICEHUB_URL is not set.")

    with Client(base_url=base_url, api_key=api_key) as client:
        project = client.projects.get(project_id=project_id)
        by_route = client.projects.get_by_route(route=project.route)

    assert by_route.project_id == project.project_id == project_id


@pytest.mark.integration
@pytest.mark.live
def test_live_cli_api_key_auth_context() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if "DICEHUB_API_KEY" not in os.environ:
        pytest.skip("DICEHUB_API_KEY is not set.")
    if "DICEHUB_URL" not in os.environ:
        pytest.skip("DICEHUB_URL is not set.")

    executable = Path(sys.executable).with_name("dicehub")
    environment = {
        "DICEHUB_API_KEY": os.environ["DICEHUB_API_KEY"],
        "DICEHUB_URL": os.environ["DICEHUB_URL"],
    }
    result = subprocess.run(
        [executable, "auth", "status", "--output", "json"],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload == {
        "schema_version": "dicehub.cli/v1",
        "ok": True,
        "data": {"identity_mode": "API_KEY"},
        "error": None,
    }


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_managed_api_key_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_MANAGED_KEY_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_MANAGED_KEY_TEST=1 to allow API-key creation and deletion.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = f"dicehub-python-live-{uuid.uuid4().hex}"

    with Client(base_url=base_url, session_cookie=cookie) as session_client:
        assert session_client.auth.context().identity_mode is IdentityMode.SESSION
        namespace_id = session_client.users.me().user_id
        baseline_ids = {
            api_key.api_key_id
            for api_key in session_client.api_keys.list(namespace_id=namespace_id)
        }

        try:
            created = session_client.api_keys.create(
                namespace_id=namespace_id,
                name=marker,
                permissions=[
                    NamespacePermission.VIEW_PROJECT_INFO,
                    NamespacePermission.VIEW_USER_PROFILE,
                ],
            )
            secret = created.value.get_secret_value()

            listed = session_client.api_keys.list(namespace_id=namespace_id)
            matches = [api_key for api_key in listed if api_key.api_key_id == created.api_key_id]
            assert matches == [ApiKey.model_validate(created.model_dump(exclude={"value"}))]
            assert not hasattr(matches[0], "value")

            with Client(base_url=base_url, api_key=secret) as api_key_client:
                context = api_key_client.auth.context()
                project_page = api_key_client.projects.list(limit=1)
            assert context.identity_mode is IdentityMode.API_KEY
            assert isinstance(project_page, ProjectPage)

            executable = Path(sys.executable).with_name("dicehub")
            environment = {
                "DICEHUB_API_KEY": secret,
                "DICEHUB_URL": base_url,
            }
            result = subprocess.run(
                [executable, "auth", "status", "--output", "json"],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
            )
            if secret in result.stdout or secret in result.stderr:
                pytest.fail("The CLI exposed the managed API key.", pytrace=False)
            assert result.returncode == 0
            assert json.loads(result.stdout) == {
                "schema_version": "dicehub.cli/v1",
                "ok": True,
                "data": {"identity_mode": "API_KEY"},
                "error": None,
            }

            session_client.api_keys.delete(api_key_id=created.api_key_id)
            remaining_ids = {
                api_key.api_key_id
                for api_key in session_client.api_keys.list(namespace_id=namespace_id)
            }
            assert created.api_key_id not in remaining_ids

            with (
                Client(base_url=base_url, api_key=secret) as revoked_client,
                pytest.raises(AuthenticationError),
            ):
                revoked_client.auth.context()
        finally:
            leftovers = session_client.api_keys.list(namespace_id=namespace_id)
            for api_key in leftovers:
                if api_key.name == marker and api_key.api_key_id not in baseline_ids:
                    session_client.api_keys.delete(api_key_id=api_key.api_key_id)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_project_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_PROJECT_MUTATION_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_PROJECT_MUTATION_TEST=1 to allow project mutations.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    name = f"dicehub-python-live-{marker}"
    slug = f"dh-sdk-live-{marker}"
    project_id: str | None = None
    delete_outcome_unknown = False

    with Client(base_url=base_url, session_cookie=cookie) as client:
        assert client.auth.context().identity_mode is IdentityMode.SESSION
        owner_id = client.users.me().user_id

        try:
            try:
                created = client.projects.create(
                    name=name,
                    slug=slug,
                    description="Temporary dicehub-python integration project",
                    visibility=ProjectVisibility.PRIVATE,
                )
            except MutationOutcomeUnknownError:
                pytest.fail(
                    f"Create outcome unknown; reconcile personal name={name!r}, slug={slug!r}.",
                    pytrace=False,
                )
            project_id = created.project_id

            fetched = client.projects.get(project_id=project_id)
            assert fetched.project_id == project_id
            assert fetched.description == "Temporary dicehub-python integration project"

            listed = client.projects.list(
                user_id=owner_id,
                search_filter=name,
                limit=20,
            )
            assert project_id in {project.project_id for project in listed.projects}

            updated_name = f"{name}-updated"
            updated_slug = f"{slug}-updated"
            client.projects.update(
                project_id=project_id,
                name=updated_name,
                slug=updated_slug,
                description="Updated by dicehub-python integration test",
            )

            updated = client.projects.get(project_id=project_id)
            assert updated.name == updated_name
            assert updated.description == "Updated by dicehub-python integration test"
            by_route = client.projects.get_by_route(route=updated.route)
            assert by_route.project_id == project_id

            try:
                client.projects.delete(project_id=project_id)
            except MutationOutcomeUnknownError:
                delete_outcome_unknown = True
                pytest.fail(
                    f"Delete outcome unknown; reconcile project ID {project_id!r}.",
                    pytrace=False,
                )
            else:
                project_id = None
        finally:
            if project_id is not None and not delete_outcome_unknown:
                try:
                    client.projects.delete(project_id=project_id)
                except MutationOutcomeUnknownError:
                    pytest.fail(
                        f"Cleanup outcome unknown; reconcile project ID {project_id!r}.",
                        pytrace=False,
                    )
