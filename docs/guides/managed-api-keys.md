---
title: Testing managed API keys locally
description: Exercise API-key administration, authentication, scoped operations, and revocation.
read_when:
  - Testing API-key catalog, creation, metadata updates, scoped use, or revocation
  - Running mutating live tests against a local dicehub instance
---

# Testing managed API keys locally

The managed-key live test uses the public GraphQL API from start to finish. It does not insert a
key directly into the database.

The test performs this lifecycle:

```text
browser session
    │
    ├── listApiKeyPermissions ──> assignable server catalog
    ├── createApiKey ──> metadata + one-time secret ──> Bearer authentication
    ├── getApiKey/listApiKeys pages ──> metadata only
    ├── updateApiKey ──> replacement name and optional complete grant set
    └── deleteApiKey ──> revoked key must return 401
```

This is a mutating test: it creates and deletes a real API key in the signed-in user's namespace.
Run it against a local or disposable dicehub account, not production.

## Prerequisites

- dicehub running at `http://localhost:8080/`
- a signed-in browser user who can manage members of their own namespace
- the development environment installed as described in the README
- the raw value of the browser's `_dicehub_session` cookie

Copy only the cookie value. Do not include `_dicehub_session=`, quotes, or a trailing semicolon.
Treat the cookie like a password and never commit it.

## Run the lifecycle test

From the `dicehub-python` repository:

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_MANAGED_KEY_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_api_key_management.py

unset DICEHUB_SESSION_COOKIE DICEHUB_LIVE_MANAGED_KEY_TEST DICEHUB_LIVE_TEST
```

`DICEHUB_API_KEY` is not needed. The test creates a key through `createApiKey`, keeps its one-time
secret in memory, and uses it as the Bearer credential.

The test uses a unique `dicehub-python-admin-<random>` name and removes only the key it created. Its
`finally` cleanup also runs when an assertion fails. A forced kill, lost network connection, or
cleanup failure can still leave a key behind; remove any remaining key with that prefix from the
dicehub API-key UI before retrying.

## Expected result

The test passes only when all of these conditions hold:

1. session authentication is reported as `SESSION`;
2. the server returns a non-empty, duplicate-free assignable permission catalog;
3. create, get, and list return complete metadata without exposing the secret;
4. the returned secret authenticates the SDK as `API_KEY` and records `lastUsedAt`;
5. name-only and complete-permission-set updates preserve immutable metadata;
6. `deleteApiKey` removes the metadata entry; and
7. reusing the revoked secret fails with an authentication error.

The SDK list call preserves its complete-tuple interface while fetching newest-first pages of 20
keys. The local lifecycle normally needs only one page; mocked contract coverage exercises multiple
pages and the fail-closed ordering, progress, aggregate, and request-count guards.

The create operation is intentionally not retried because it is not idempotent. The plaintext
secret is returned only by creation; listing returns metadata such as ID, name, prefix,
permissions, timestamps, and status, never the secret.

The server authorizes every management operation. Only an authenticated session can inspect the
catalog or create, get, list, update, and revoke managed keys. API-key identities cannot manage or
delegate other keys.

## CLI administration

Every `dicehub api-key` command requires `DICEHUB_SESSION_COOKIE` and rejects
`DICEHUB_API_KEY`. Query the server-owned catalog before choosing grants. Creation writes its raw
one-time secret only to the required non-stdio pipe or socket; JSON remains metadata-only:

```bash
dicehub api-key permissions "$DICEHUB_NAMESPACE_ID" --output json
dicehub api-key create "$DICEHUB_NAMESPACE_ID" \
  --name "automation agent" \
  --permission VIEW_PROJECT_INFO \
  --secret-fd 3 \
  --output json \
  3> >(your-secret-manager write dicehub/automation-agent)

dicehub api-key list "$DICEHUB_NAMESPACE_ID" --output json
dicehub api-key get "$DICEHUB_NAMESPACE_ID" "$DICEHUB_API_KEY_ID" --output json
dicehub api-key update "$DICEHUB_NAMESPACE_ID" "$DICEHUB_API_KEY_ID" \
  --name "renamed automation agent" \
  --permission VIEW_RUN_INFO \
  --output json
dicehub api-key revoke "$DICEHUB_API_KEY_ID" --yes --output json
```

Use only permissions returned by the catalog for that namespace. Omitting every update
`--permission` preserves the existing grants; supplying the option replaces the complete set. Do
not replay create, update, or revoke after `MUTATION_OUTCOME_UNKNOWN`; reconcile the exact scope,
name, and key ID first.

## App-discovery lifecycle

The app-discovery test selects an existing private or internal app, creates a temporary
project-scoped key with `VIEW_APP_INFO`, exercises list/get/get-by-route through both the SDK and
CLI, revokes the key, and verifies the next read returns an authentication failure. It never
creates, changes, or deletes an app.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_APP_API_KEY_DISCOVERY_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_app_api_key_discovery.py
```

The only mutation is the temporary API key. Cleanup matches its exact ID and unique name; an
interrupted process can still leave the key behind for manual removal.

## Configuration-discovery lifecycle

The configuration-discovery test selects a private or internal app with an existing config, then
creates a temporary project-scoped key carrying only `VIEW_CONFIG_INFO`. It exercises config list
and get through both the SDK and CLI, proves the narrow key cannot read app metadata, revokes the
key, and verifies the next config read fails authentication. It does not read config files or
mutate apps or configurations.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_CONFIG_API_KEY_DISCOVERY_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_config_api_key_discovery.py
```

The only mutation is the temporary API key. Cleanup matches its exact ID and unique name; an
interrupted process can still leave the key behind for manual removal.

## Configuration-creation lifecycle

The configuration-creation test creates a temporary project and app through the session, then a
project-scoped key carrying only `CREATE_CONFIG`. The key creates one configuration through the SDK
from the app default and one through the installed CLI from the first configuration. It must fail
against an app in a sibling project and when given a cross-app source ID. The test revokes the key
and deletes both temporary projects.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_CONFIG_API_KEY_CREATE_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_config_api_key_create.py
```

Creation is never retried after an ambiguous outcome. Exact project and key IDs drive cleanup;
cleanup failures report every ID requiring manual reconciliation.

## App-creation lifecycle

The app-creation test creates a temporary personal project through the session, then creates a
project-scoped key carrying only `CREATE_APP`. That key creates one app through the SDK and one
through the installed CLI using an existing source template. The test revokes the key, verifies
that it no longer authenticates, and deletes the temporary project and its apps.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_APP_API_KEY_CREATE_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_app_api_key_create.py
```

The test discovers a source template ID from an existing app. It skips when the account has no app
with a template. Creation is never retried after an ambiguous outcome; exact temporary project and
key IDs drive cleanup, and cleanup failures report the IDs that require manual reconciliation.

## App-metadata-update lifecycle

The app-update test creates two temporary projects and one app in each. A project-scoped key with
only `EDIT_APP_INFO` updates the target app through both the SDK and CLI. The same key must fail to
update the control app in the sibling project. Session reads verify both states because the narrow
edit grant deliberately does not imply `VIEW_APP_INFO`.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_APP_API_KEY_UPDATE_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_app_api_key_update.py
```

The test revokes the temporary key and verifies that it no longer authenticates. Exact project and
key IDs drive cleanup. An ambiguous app update is never retried; inspect the exact app ID before
deciding whether another mutation is safe.

## App-deletion lifecycle

The app-deletion test creates target and control projects with temporary apps. A project-scoped
key carrying only `DELETE_APP` must delete one target app through the SDK and another through the
installed CLI. The same key must fail against the control app in the sibling project, and it must
remain active after its target apps are gone.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_APP_API_KEY_DELETE_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_app_api_key_delete.py
```

The CLI path requires `--yes`. The test then revokes the temporary key and proves the secret no
longer authenticates. Exact project and key IDs drive cleanup. An ambiguous app deletion is never
retried; use an independently authorized session to reconcile the exact app ID. Project cleanup is
a separate session-authorized operation and reports every ID needing manual reconciliation.

## Run-discovery lifecycle

The run-discovery test selects an existing private or internal app run, then creates a temporary
project-scoped key carrying only `VIEW_RUN_INFO`. It exercises run list, get, and status through the
SDK and installed CLI, proves the narrow key cannot read app metadata or a run in a sibling project,
revokes the key, and verifies the next status read fails authentication. It never changes the run.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_RUN_API_KEY_DISCOVERY_TEST=1
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_run_api_key_discovery.py
```

The only mutation is the temporary API key. The test skips if the account has no suitable existing
run. Cleanup matches the key's exact ID and unique name; an interrupted process can still leave the
key behind for manual removal.

## Run start/stop lifecycle

The run-mutation test is intentionally not part of general live testing. It starts one run on an
explicit disposable configuration, which may consume quota or incur charges and transactionally
archives that configuration's prior terminal run as part of replacement. It leaves the successfully
created, stopped run in dicehub's history. Use a target reserved for this test.

The test creates two project-scoped keys: one with only `START_RUN`, and one with only `STOP_RUN`.
The start key creates the run through the SDK but cannot stop it. The stop key requests the exact
run's interruption through the installed CLI. Hermetic server tests separately pin that a
`STOP_RUN`-only key cannot start a run without risking a second charged live mutation. Both
temporary keys are revoked afterward. Start explicitly uses `notify=False` because a managed key
has no human notification recipient. An accepted stop is asynchronous and the test does not claim
a terminal state.

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_RUN_API_KEY_MUTATION_TEST=1
export DICEHUB_LIVE_RUN_PROJECT_ID=42
export DICEHUB_LIVE_RUN_APP_ID=101
export DICEHUB_LIVE_RUN_CONFIG_ID=301
export DICEHUB_LIVE_RUN_MACHINE_TYPE_ID=local
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
printf '\n'

pytest -m "live and mutating" \
  tests/integration/test_live_run_api_key_mutations.py
```

The four IDs must describe the same fixed project subtree and exact configuration. A known run ID
is stopped once during cleanup if start succeeded but the normal stop request was never sent. If a
mutation outcome is unknown, the test reports exact IDs for manual reconciliation and does not
blindly replay the request.

## SDK lifecycle

The executable [`manage_api_keys.py`](../../examples/manage_api_keys.py) example discovers the
session's assignable catalog, creates a key, gets and updates its metadata, authenticates with its
one-time secret in memory, and revokes it. Cleanup matches both a unique name and an ID absent from
the pre-run baseline.

```bash
export DICEHUB_URL=http://localhost:8080
read -rsp "dicehub session cookie: " DICEHUB_SESSION_COOKIE
export DICEHUB_SESSION_COOKIE
python examples/manage_api_keys.py
unset DICEHUB_SESSION_COOKIE
```

`SecretStr` masks accidental representation and JSON serialization. Calling `get_secret_value()`
deliberately reveals the credential, so keep that value in memory or a secret manager only.
