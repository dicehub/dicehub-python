"""List permission-scoped group user and team memberships as JSON."""

from __future__ import annotations

import json
import os

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        group_id = os.environ["DICEHUB_GROUP_ID"]
        users = client.groups.list_user_members(group_id=group_id, limit=20)
        teams = client.groups.list_team_members(group_id=group_id, limit=20)

    print(
        json.dumps(
            {
                "users": users.model_dump(mode="json"),
                "teams": teams.model_dump(mode="json"),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
