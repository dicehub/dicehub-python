"""Update one group with an API key granted EDIT_GROUP_INFO."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    group_id = os.environ["DICEHUB_GROUP_ID"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.groups.update(
                group_id=group_id,
                description=os.environ["DICEHUB_GROUP_DESCRIPTION"],
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile group ID {group_id!r}; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"group_id": group_id}))


if __name__ == "__main__":
    main()
