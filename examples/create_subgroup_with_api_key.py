"""Create one subgroup with an API key granted CREATE_SUBGROUP."""

from __future__ import annotations

import os
import sys

import dicehub as dh


def main() -> None:
    parent_id = os.environ["DICEHUB_PARENT_GROUP_ID"]
    name = os.environ["DICEHUB_GROUP_NAME"]
    slug = os.environ["DICEHUB_GROUP_SLUG"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            group = client.groups.create(
                parent_id=parent_id,
                name=name,
                slug=slug,
                description=os.environ.get("DICEHUB_GROUP_DESCRIPTION"),
                visibility=dh.GroupVisibility.PRIVATE,
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile subgroup name {name!r} under parent ID {parent_id!r}; "
                "do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(group.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
