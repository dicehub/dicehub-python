from __future__ import annotations

import os
import uuid

import pytest

from dicehub import (
    Client,
    MembershipVisibility,
    MutationOutcomeUnknownError,
    ProjectVisibility,
)


@pytest.mark.integration
@pytest.mark.live
@pytest.mark.mutating
def test_live_app_membership_lifecycle() -> None:
    if os.environ.get("DICEHUB_LIVE_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_TEST=1 to run the local API smoke test.")
    if os.environ.get("DICEHUB_LIVE_APP_MEMBERSHIP_TEST") != "1":
        pytest.skip("Set DICEHUB_LIVE_APP_MEMBERSHIP_TEST=1 to allow app membership mutations.")

    cookie = os.environ.get("DICEHUB_SESSION_COOKIE")
    if cookie is None:
        pytest.skip("DICEHUB_SESSION_COOKIE is not set.")
    template_id = os.environ.get("DICEHUB_LIVE_APP_TEMPLATE_ID")
    if template_id is None:
        pytest.skip("DICEHUB_LIVE_APP_TEMPLATE_ID is not set.")

    base_url = os.environ.get("DICEHUB_URL", "http://127.0.0.1:8080")
    marker = uuid.uuid4().hex
    project_id: str | None = None
    app_id: str | None = None
    member_id: str | None = None
    membership_added = False
    cleanup_failures: list[str] = []

    with Client(base_url=base_url, session_cookie=cookie) as client:
        try:
            member_id = client.users.me().user_id
            project = client.projects.create(
                name=f"dicehub-python-app-members-{marker}",
                slug=f"dh-app-members-{marker}",
                description="Temporary app membership integration project",
                visibility=ProjectVisibility.PRIVATE,
            )
            project_id = project.project_id
            app = client.apps.create(
                project_id=project_id,
                template_id=template_id,
                name=f"App members {marker}",
            )
            app_id = app.app_id
            role = client.apps.get_role_by_name(app_id=app_id, name="OWNER")

            try:
                client.apps.add_member(
                    app_id=app_id,
                    member_id=member_id,
                    role_id=role.role_id,
                    visibility=MembershipVisibility.PRIVATE,
                )
            except MutationOutcomeUnknownError:
                membership_added = True
                pytest.fail(
                    f"Add outcome unknown; reconcile app ID {app_id!r} and member ID "
                    f"{member_id!r}.",
                    pytrace=False,
                )
            membership_added = True

            direct = client.apps.list_user_members(
                app_id=app_id,
                include_inherited=False,
                limit=50,
            )
            assert any(
                membership.member_id == member_id and not membership.inherited
                for membership in direct.memberships
            )

            client.apps.update_member(
                app_id=app_id,
                member_id=member_id,
                visibility=MembershipVisibility.PUBLIC,
            )
            updated = client.apps.list_user_members(
                app_id=app_id,
                include_inherited=False,
                limit=50,
            )
            assert any(
                membership.member_id == member_id
                and membership.visibility is MembershipVisibility.PUBLIC
                and membership.role_id == role.role_id
                for membership in updated.memberships
            )

            try:
                client.apps.remove_member(app_id=app_id, member_id=member_id)
            except MutationOutcomeUnknownError:
                membership_added = False
                pytest.fail(
                    f"Remove outcome unknown; reconcile app ID {app_id!r} and member ID "
                    f"{member_id!r}. Do not retry automatically.",
                    pytrace=False,
                )
            membership_added = False
            remaining = client.apps.list_user_members(
                app_id=app_id,
                include_inherited=False,
                limit=50,
            )
            assert member_id not in {membership.member_id for membership in remaining.memberships}
        finally:
            if membership_added and app_id is not None and member_id is not None:
                try:
                    client.apps.remove_member(app_id=app_id, member_id=member_id)
                except Exception:
                    cleanup_failures.append(
                        f"Membership cleanup failed; reconcile app ID {app_id!r} and member "
                        f"ID {member_id!r}."
                    )
            if project_id is not None:
                try:
                    client.projects.delete(project_id=project_id)
                except Exception:
                    cleanup_failures.append(
                        f"Project cleanup failed; reconcile project ID {project_id!r}."
                    )
            if cleanup_failures:
                pytest.fail(" ".join(cleanup_failures), pytrace=False)
