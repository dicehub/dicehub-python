---
title: Managed API keys
description: Create, list, and revoke namespace-scoped dicehub API keys.
read_when:
  - Automating API-key lifecycle operations
  - Reviewing one-time secret handling
---

# Managed API keys

## Create the first hosted key

Sign in to `https://dicehub.com`, then open
[API-key settings](https://dicehub.com/settings/tokens/create). Create a personal-scoped key with a
clear name, a short expiration, and only `VIEW_PROJECT_INFO` for the first read-only project
workflow. Review the scope and permission before creation.

The secret appears once after creation. Move it directly to a secret manager before you leave the
page. The API-key list shows metadata and a prefix, not the secret. Never put the value in a command
argument, URL, source file, project configuration, log, or error report.

There is no in-place secret rotation. Create a replacement, update and verify the consumer, then
revoke the old key at [API-key settings](https://dicehub.com/settings/tokens). Revocation is
immediate. A lost secret must be revoked and replaced.

Minimum personal-scope grants for the first workflows are:

| Workflow | Permission |
|---|---|
| `client.auth.context()` or `dicehub auth status` | No resource permission is consumed; select only `VIEW_PROJECT_INFO` because the web form requires one grant |
| `client.projects.list()` | `VIEW_PROJECT_INFO` |
| `client.projects.create()` with no `group_id` | `CREATE_USER_PROJECT` |

Do not grant both read and mutation permissions unless one process needs both operations.

## Manage keys through the SDK

The SDK exposes managed keys through `client.api_keys`. The following fragment assumes `client` is
an authenticated session client and `dicehub` was imported as `dh`:

```python
from datetime import datetime, timedelta, timezone

created = client.api_keys.create(
    namespace_id="42",
    name="ci agent",
    permissions=[dh.NamespacePermission.VIEW_PROJECT_INFO],
    expires_at=(
        datetime.now(timezone.utc).replace(microsecond=0)
        + timedelta(days=30)
    ),
)
secret = created.value.get_secret_value()
listed = client.api_keys.list(namespace_id="42")
client.api_keys.delete(api_key_id=created.api_key_id)
```

Creation returns the plaintext value once as `SecretStr`. Listing requests metadata only and its
model has no secret field. Revealing `SecretStr` is an explicit handoff to a secret manager or a
new in-memory client; do not print or persist it.

Creation accepts optional timezone-aware `not_before` and `expires_at` values with millisecond
precision. Omit `not_before` to activate immediately. Omit `expires_at` to keep the key valid until
revocation. Existing keys without validity metadata remain active. The server uses its database
clock and the half-open interval `not_before <= now < expires_at` on every authentication request.

Metadata includes `not_before`, `expires_at`, and `validity_status`. The validity status is
`ACTIVE`, `NOT_YET_ACTIVE`, or `EXPIRED`. The older `status` field remains `ACTIVE` for compatibility.
Validity can be set only during creation in this release. Revoke and recreate a key instead of
extending or reactivating it.

`list()` keeps its original public signature and returns one complete, newest-first tuple. Internally
it requests fixed pages of 20 keys using the last numeric key ID as an exclusive cursor. Each HTTP
response remains subject to the SDK's 64 KiB limit, while the combined tuple may be larger than one
response. The SDK rejects oversized, duplicate, out-of-order, or non-progressing pages instead of
returning incomplete or ambiguous metadata. Cursor IDs must also fit the server's signed 64-bit
namespace-ID range. The SDK refuses to aggregate more than 10,000 keys or make more than 501 list
requests. The paginated GraphQL contract and SDK must be deployed together; the SDK does not fall
back to the former unbounded query.

The server authorizes all operations, and only an authenticated session can manage keys. API-key
identities cannot create or delegate other keys. Creation and deletion are not automatically
retried.

The session-only CLI exposes the same lifecycle as `dicehub api-key list`, `get`, `permissions`,
`create`, `update`, and `revoke`. Creation requires `--secret-fd FD`, where `FD` is an already-open
writable pipe or socket numbered `3` or higher that does not alias stdin, stdout, or stderr. Only
that descriptor receives the raw one-time secret; normal JSON and text output contain metadata only.
Terminals and regular files are rejected. Connect the descriptor directly to a trusted secret
manager:

```bash
unset DICEHUB_API_KEY
export DICEHUB_URL=https://dicehub.com
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
dicehub api-key create "$DICEHUB_NAMESPACE_ID" \
  --name "ci agent" \
  --permission VIEW_PROJECT_INFO \
  --expires-at "2026-09-16T12:00:00Z" \
  --secret-fd 3 \
  3> >(your-secret-manager write dicehub/ci-agent)
```

`update` requires a replacement name. Repeated `--permission` options replace the entire grant set;
omitting them preserves it. `revoke` maps to the SDK's `delete` operation and requires the exact key
ID plus `--yes`. Neither mutation is retried after an ambiguous outcome.

A managed key with `VIEW_GROUP_INFO` can list and resolve group metadata inside its fixed scope.
The independent `EDIT_GROUP_INFO` grant can change the group name, slug, description, and
visibility in that scope. Neither grant exposes memberships, projects, apps, or billing. See
[Groups](groups.md) for the complete boundary.

A personal-scoped key with `CREATE_USER_PROJECT`, or a group-scoped key with `CREATE_PROJECT`, can
create projects only inside that fixed scope. A project-scoped key cannot create a sibling project.
See [Projects](projects.md) for the SDK, CLI, and ambiguous-outcome rules.

`VIEW_PUBLIC_APP_MEMBERS` and `VIEW_PRIVATE_APP_MEMBERS` list memberships with the matching
visibility inside the key's fixed scope. `MANAGE_APP_MEMBERS` permits direct user and team
membership changes and target-scoped username lookup. Add `VIEW_APP_INFO` when the automation must
resolve the app or its assignable roles. Resolving a team-route selector also needs
`VIEW_TEAM_INFO`. See [Apps](apps.md) for inheritance and mutation rules.

A managed key with `VIEW_RUN_INFO` can list and inspect only safe run metadata inside its fixed
scope. It cannot read run inputs, outputs, environment, logs, reports, archives, or app metadata.
`DOWNLOAD_RUN_RESULT` independently permits the bounded result ZIP download. `START_RUN` and
`STOP_RUN` permit only those exact mutations without implying metadata access or each other.
Managed keys must start with `notify=False`; automation identities have no human notification
recipient. See [Runs](runs.md) for effects, confirmation, and ambiguous-outcome rules.

See the [managed API-key live-test guide](guides/managed-api-keys.md) for the complete lifecycle and
cleanup procedure.
