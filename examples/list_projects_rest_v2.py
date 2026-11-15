"""Read projects through REST v2 on a deployment that enables it."""

from __future__ import annotations

import json
import os

from dicehub import Client


def main() -> None:
    with Client(
        base_url=os.environ.get("DICEHUB_URL", "https://dicehub.com"),
        api_key=os.environ["DICEHUB_API_KEY"],
        project_reads="rest_v2",
    ) as client:
        page = client.projects.list(limit=20)
        print(json.dumps(page.model_dump(mode="json"), ensure_ascii=True))
        if page.projects:
            detail = client.projects.get(project_id=page.projects[0].project_id)
            assert client.projects.get_by_route(route=detail.route) == detail


if __name__ == "__main__":
    main()
