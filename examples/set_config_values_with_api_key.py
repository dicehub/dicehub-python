"""Set scalar values in one YAML configuration resource."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    config_id = os.environ["DICEHUB_CONFIG_ID"]
    yaml_path = os.environ.get("DICEHUB_CONFIG_YAML_PATH", "solver/control.yaml")
    updates = (
        dh.ConfigValueUpdate(path=("controlDict", "endTime"), value=200),
        dh.ConfigValueUpdate(path=("controlDict", "writeInterval"), value=20),
        dh.ConfigValueUpdate(path=("controlDict", "writeAscii"), value=True),
    )

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.configs.set_values(
                config_id=config_id,
                path=yaml_path,
                updates=updates,
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Reconcile config ID {config_id!r}, YAML path {yaml_path!r}, and value paths; "
                "do not retry.",
                file=sys.stderr,
            )
            raise

    print(
        json.dumps(
            {
                "config_id": config_id,
                "path": yaml_path,
                "updated_paths": [list(update.path) for update in updates],
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
