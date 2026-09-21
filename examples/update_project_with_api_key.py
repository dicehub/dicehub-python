"""Update one project with an API key granted EDIT_PROJECT_INFO."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    project_id = os.environ["DICEHUB_PROJECT_ID"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.projects.update(
                project_id=project_id,
                description=os.environ["DICEHUB_PROJECT_DESCRIPTION"],
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile project ID {project_id!r}; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"project_id": project_id}))


if __name__ == "__main__":
    main()
