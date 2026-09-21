"""Update config metadata with an API key granted EDIT_CONFIG_INFO."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    config_id = os.environ["DICEHUB_CONFIG_ID"]
    name = os.environ.get("DICEHUB_CONFIG_NAME")
    description = os.environ.get("DICEHUB_CONFIG_DESCRIPTION")
    if name is None and description is None:
        raise SystemExit("Set DICEHUB_CONFIG_NAME or DICEHUB_CONFIG_DESCRIPTION.")

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.configs.update(
                config_id=config_id,
                name=name,
                description=description,
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile config ID {config_id!r}; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"config_id": config_id}))


if __name__ == "__main__":
    main()
