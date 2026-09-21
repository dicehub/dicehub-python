"""Create a project with CREATE_USER_PROJECT or CREATE_PROJECT in the matching scope."""

from __future__ import annotations

import os
import sys

import dicehub as dh


def main() -> None:
    group_id = os.environ.get("DICEHUB_PROJECT_GROUP_ID")
    name = os.environ["DICEHUB_PROJECT_NAME"]
    slug = os.environ["DICEHUB_PROJECT_SLUG"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            created = client.projects.create(
                name=name,
                slug=slug,
                group_id=group_id,
                description=os.environ.get("DICEHUB_PROJECT_DESCRIPTION"),
                visibility=dh.ProjectVisibility.PRIVATE,
            )
        except dh.MutationOutcomeUnknownError:
            scope = f"group ID {group_id!r}" if group_id is not None else "personal namespace"
            print(
                f"Reconcile name={name!r}, slug={slug!r} within {scope}; do not retry.",
                file=sys.stderr,
            )
            raise

    print(created.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
