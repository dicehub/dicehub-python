from __future__ import annotations

import json
import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        machine_types = client.runs.list_machine_types()

    for machine_type in machine_types:
        print(json.dumps(machine_type.model_dump(mode="json"), ensure_ascii=True))


if __name__ == "__main__":
    main()
