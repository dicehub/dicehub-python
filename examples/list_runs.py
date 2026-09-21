from __future__ import annotations

import json
import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        page = client.runs.list(
            namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
            include_descendants=True,
            order=dh.SortOrder.DESC,
            limit=20,
        )

    for run in page.runs:
        print(json.dumps(run.model_dump(mode="json"), ensure_ascii=True))


if __name__ == "__main__":
    main()
