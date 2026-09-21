"""Delete one exact app with an API key granted DELETE_APP."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    app_id = os.environ["DICEHUB_APP_ID"]
    if os.environ.get("DICEHUB_CONFIRM_DELETE_APP_ID") != app_id:
        raise SystemExit(
            "Set DICEHUB_CONFIRM_DELETE_APP_ID to the exact DICEHUB_APP_ID to confirm deletion."
        )

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.apps.delete(app_id=app_id)
        except dh.MutationOutcomeUnknownError:
            print(
                f"App ID {app_id!r} may already be deleted; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"deleted_app_id": app_id}))


if __name__ == "__main__":
    main()
