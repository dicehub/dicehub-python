"""List permission-scoped group summaries as JSON."""

from __future__ import annotations

import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        page = client.groups.list(limit=20)

    print(page.model_dump_json(ensure_ascii=True))


if __name__ == "__main__":
    main()
