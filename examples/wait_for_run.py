"""Wait for one existing dicehub run with a finite deadline."""

from __future__ import annotations

import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        status = client.runs.wait(
            run_id=os.environ["DICEHUB_RUN_ID"],
            timeout_seconds=3600,
            poll_seconds=2,
        )
    print(status.run_id, status.state.value)


if __name__ == "__main__":
    main()
