"""Update app metadata with an API key granted EDIT_APP_INFO."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    app_id = os.environ["DICEHUB_APP_ID"]

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.apps.update(
                app_id=app_id,
                description=os.environ["DICEHUB_APP_DESCRIPTION"],
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile app ID {app_id!r}; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"app_id": app_id}))


if __name__ == "__main__":
    main()
