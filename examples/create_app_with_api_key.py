"""Create an app with CREATE_APP inside the key's fixed namespace scope."""

from __future__ import annotations

import os
import sys

import dicehub as dh


def main() -> None:
    project_id = os.environ["DICEHUB_PROJECT_ID"]
    template_route = os.environ["DICEHUB_TEMPLATE_ROUTE"]
    name = os.environ["DICEHUB_APP_NAME"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        template = client.templates.get_by_route(route=template_route)
        try:
            created = client.apps.create(
                project_id=project_id,
                template_id=template.template_id,
                name=name,
                description=os.environ.get("DICEHUB_APP_DESCRIPTION"),
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile name={name!r} inside project ID {project_id!r}; do not retry.",
                file=sys.stderr,
            )
            raise

    print(created.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
