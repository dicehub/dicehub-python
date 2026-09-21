"""Download one result ZIP with a key granted DOWNLOAD_RUN_RESULT."""

from __future__ import annotations

import json
import os
from pathlib import Path

import dicehub as dh


def main() -> None:
    run_id = os.environ["DICEHUB_RUN_ID"]
    destination = Path(os.environ["DICEHUB_RUN_RESULTS_DESTINATION"])
    if not destination.parent.is_dir():
        raise SystemExit("DICEHUB_RUN_RESULTS_DESTINATION parent directory must exist.")

    created = False
    try:
        with destination.open("xb") as stream:
            created = True
            with dh.Client(
                api_key=os.environ["DICEHUB_API_KEY"],
            ) as client:
                count = client.runs.download_results(
                    run_id=run_id,
                    destination=stream,
                )
        created = False
    except FileExistsError:
        raise SystemExit("DICEHUB_RUN_RESULTS_DESTINATION already exists.") from None
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise

    print(json.dumps({"run_id": run_id, "destination": str(destination), "bytes": count}))


if __name__ == "__main__":
    main()
