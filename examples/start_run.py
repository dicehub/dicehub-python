"""Start one exact config with an API key granted START_RUN."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    config_id = os.environ["DICEHUB_CONFIG_ID"]
    if os.environ.get("DICEHUB_CONFIRM_START_CONFIG_ID") != config_id:
        raise SystemExit("DICEHUB_CONFIRM_START_CONFIG_ID must exactly match DICEHUB_CONFIG_ID.")

    cpu_count_value = os.environ.get("DICEHUB_CPU_COUNT")
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            status = client.runs.start(
                config_id=config_id,
                machine_type_id=os.environ["DICEHUB_MACHINE_TYPE_ID"],
                node_count=int(os.environ.get("DICEHUB_NODE_COUNT", "1")),
                cpu_count=int(cpu_count_value) if cpu_count_value is not None else None,
                notify=False,
            )
        except dh.MutationOutcomeUnknownError:
            print(
                f"Start outcome unknown for config ID {config_id!r}; a run may have been "
                "created. Do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"run_status": status.model_dump(mode="json")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
