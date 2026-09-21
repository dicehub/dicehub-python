"""Manage a short-lived project with create, view, edit, and delete API-key grants."""

from __future__ import annotations

import os
import sys
import uuid

import dicehub as dh


def main() -> None:
    marker = uuid.uuid4().hex
    name = f"dicehub-python-example-{marker}"
    slug = f"dh-sdk-{marker}"
    created_project_id: str | None = None
    delete_outcome_unknown = False

    with dh.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
        try:
            try:
                created = client.projects.create(
                    name=name,
                    slug=slug,
                    description="Temporary dicehub-python lifecycle example",
                    visibility=dh.ProjectVisibility.PRIVATE,
                )
            except dh.MutationOutcomeUnknownError:
                print(
                    f"Reconcile the personal project name={name!r}, slug={slug!r} manually.",
                    file=sys.stderr,
                )
                raise
            created_project_id = created.project_id

            client.projects.update(
                project_id=created_project_id,
                name=f"{name}-updated",
                slug=f"{slug}-updated",
                description="Updated by the lifecycle example",
            )
            updated = client.projects.get(project_id=created_project_id)
            by_route = client.projects.get_by_route(route=updated.route)
            if by_route.project_id != created_project_id:
                raise RuntimeError("dicehub resolved a different project.")

            print(updated.model_dump_json(ensure_ascii=True))

            try:
                client.projects.delete(project_id=created_project_id)
            except dh.MutationOutcomeUnknownError:
                delete_outcome_unknown = True
                print(
                    f"Reconcile deletion of project ID {created_project_id!r} manually.",
                    file=sys.stderr,
                )
                raise
            else:
                created_project_id = None
        finally:
            if created_project_id is not None and not delete_outcome_unknown:
                try:
                    client.projects.delete(project_id=created_project_id)
                except dh.MutationOutcomeUnknownError:
                    print(
                        f"Reconcile deletion of project ID {created_project_id!r} manually.",
                        file=sys.stderr,
                    )
                    raise


if __name__ == "__main__":
    main()
