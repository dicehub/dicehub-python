"""Delete one in-scope group with an API key granted DELETE_GROUP."""

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
            client.groups.delete(group_id=group_id)
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile group ID {group_id!r}; do not retry deletion automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"group_id": group_id}))


if __name__ == "__main__":
    main()
