"""Request a stop for one exact run with an API key granted STOP_RUN."""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    run_id = os.environ["DICEHUB_RUN_ID"]
    if os.environ.get("DICEHUB_CONFIRM_STOP_RUN_ID") != run_id:
        raise SystemExit("DICEHUB_CONFIRM_STOP_RUN_ID must exactly match DICEHUB_RUN_ID.")

    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        try:
            client.runs.stop(run_id=run_id)
        except dh.MutationOutcomeUnknownError:
            print(
                f"Stop outcome unknown for run ID {run_id!r}; interruption may have been "
                "requested. Do not retry automatically.",
                file=sys.stderr,
            )
            raise

    print(json.dumps({"stop_requested_for_run_id": run_id}, ensure_ascii=True))


if __name__ == "__main__":
    main()
