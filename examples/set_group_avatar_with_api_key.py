"""Set one group avatar with an API key granted group view and edit access."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import dicehub as dh


def main() -> None:
    group_id = os.environ["DICEHUB_GROUP_ID"]
    source_path = Path(os.environ["DICEHUB_GROUP_AVATAR"])

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            with source_path.open("rb") as source:
                client.groups.set_avatar(group_id=group_id, source=source)
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile the avatar for group ID {group_id!r}; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"group_id": group_id}))


if __name__ == "__main__":
    main()
