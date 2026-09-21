"""Resolve exact selectors and optionally add one user to an app.

Set DICEHUB_APPLY_MEMBERSHIP=1 to send the ID-only mutation.
"""

from __future__ import annotations

import json
import os
import sys

import dicehub as dh


def main() -> None:
    with dh.Client(
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        app = client.apps.get_by_route(route=os.environ["DICEHUB_APP_ROUTE"])
        user = client.users.resolve_membership_candidate(
            namespace_id=app.app_id,
            username=os.environ["DICEHUB_MEMBER_USERNAME"],
        )
        role = client.apps.get_role_by_name(
            app_id=app.app_id,
            name=os.environ["DICEHUB_APP_ROLE"],
        )
        resolved = {
            "app_id": app.app_id,
            "member_id": user.user_id,
            "role_id": role.role_id,
        }
        print(json.dumps(resolved, ensure_ascii=True))
        if os.environ.get("DICEHUB_APPLY_MEMBERSHIP") != "1":
            return
        try:
            client.apps.add_member(
                app_id=app.app_id,
                member_id=user.user_id,
                role_id=role.role_id,
            )
        except dh.MutationOutcomeUnknownError:
            print("Reconcile the resolved IDs; do not retry automatically.", file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
