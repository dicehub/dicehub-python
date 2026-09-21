"""Delete one exact non-default config with an API key granted DELETE_CONFIG."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    config_id = os.environ["DICEHUB_CONFIG_ID"]
    if os.environ.get("DICEHUB_CONFIRM_DELETE_CONFIG_ID") != config_id:
        raise SystemExit(
            "Set DICEHUB_CONFIRM_DELETE_CONFIG_ID to the exact DICEHUB_CONFIG_ID to confirm "
            "deletion."
        )

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.configs.delete(config_id=config_id)
        except dh.MutationOutcomeUnknownError:
            print(
                f"Config ID {config_id!r} may already be deleted; do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"deleted_config_id": config_id}))


if __name__ == "__main__":
    main()
