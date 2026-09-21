"""Create a config with CREATE_CONFIG inside the key's fixed namespace scope."""

from __future__ import annotations

import os
import sys

import dicehub as dh


def main() -> None:
    app_id = os.environ["DICEHUB_APP_ID"]
    name = os.environ.get("DICEHUB_CONFIG_NAME")

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            created = client.configs.create(
                app_id=app_id,
                source_config_id=os.environ.get("DICEHUB_SOURCE_CONFIG_ID"),
                name=name,
                description=os.environ.get("DICEHUB_CONFIG_DESCRIPTION"),
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile name={name!r} inside app ID {app_id!r}; do not retry.",
                file=sys.stderr,
            )
            raise

    print(created.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
