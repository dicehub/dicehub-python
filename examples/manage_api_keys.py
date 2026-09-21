"""Manage and use a short-lived API key through a browser session."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import dicehub as dh


def main() -> None:
    base_url = os.environ.get("DICEHUB_URL", "https://dicehub.com")
    marker = f"dicehub-python-example-{uuid.uuid4().hex}"
    renamed = f"{marker}-renamed"
    revoke_outcome_unknown = False

    with dh.Client(
        base_url=base_url,
        session_cookie=os.environ["DICEHUB_SESSION_COOKIE"],
    ) as session_client:
        namespace_id = session_client.users.me().user_id
        baseline_ids = {
            item.api_key_id for item in session_client.api_keys.list(namespace_id=namespace_id)
        }
        try:
            catalog = session_client.api_keys.list_permissions(namespace_id=namespace_id)
            if not catalog:
                raise RuntimeError("The session cannot assign API-key permissions in this scope.")

            created = session_client.api_keys.create(
                namespace_id=namespace_id,
                name=marker,
                permissions=[catalog[0]],
                expires_at=(datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)),
            )
            fetched = session_client.api_keys.get(
                namespace_id=namespace_id,
                api_key_id=created.api_key_id,
            )
            assert fetched is not None
            updated = session_client.api_keys.update(
                namespace_id=namespace_id,
                api_key_id=created.api_key_id,
                name=renamed,
                permissions=[catalog[-1]],
            )
            with dh.Client(
                base_url=base_url,
                api_key=created.value.get_secret_value(),
            ) as api_key_client:
                identity_mode = api_key_client.auth.context().identity_mode

            print(f"{updated.api_key_id}\t{identity_mode.value}")
            try:
                session_client.api_keys.delete(api_key_id=created.api_key_id)
            except dh.MutationOutcomeUnknownError:
                revoke_outcome_unknown = True
                raise
        finally:
            if not revoke_outcome_unknown:
                for item in session_client.api_keys.list(namespace_id=namespace_id):
                    if item.name in {marker, renamed} and item.api_key_id not in baseline_ids:
                        session_client.api_keys.delete(api_key_id=item.api_key_id)


if __name__ == "__main__":
    main()
