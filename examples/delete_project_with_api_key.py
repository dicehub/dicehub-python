"""Delete one exact project with an API key granted DELETE_PROJECT."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    project_id = os.environ["DICEHUB_PROJECT_ID"]
    if os.environ.get("DICEHUB_CONFIRM_DELETE_PROJECT_ID") != project_id:
        raise SystemExit("DICEHUB_CONFIRM_DELETE_PROJECT_ID must exactly match DICEHUB_PROJECT_ID.")

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.projects.delete(project_id=project_id)
        except dh.MutationOutcomeUnknownError:
            print(
                f"Deletion outcome unknown; reconcile project ID {project_id!r}. Do not retry.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"deleted_project_id": project_id}, ensure_ascii=True))


if __name__ == "__main__":
    main()
