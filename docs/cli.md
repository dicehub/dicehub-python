---
title: CLI
description: Stable commands and machine-readable output from the dicehub executable.
read_when:
  - Calling dicehub from shell automation
  - Adding or changing a CLI command
---

# CLI

The CLI is a thin adapter over the Python client:

```bash
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub auth status --output json
```

Successful and operational-error JSON use the `dicehub.cli/v1` envelope. Typer usage errors retain
their normal exit code and formatting.

Credential and URL options are intentionally absent. Values come from trusted environment
injection, not command arguments that can appear in process listings or shell history.

`https://dicehub.com` is the default origin. Set `DICEHUB_URL` when you use another deployment.

Group, project, app, config, run, and template automation normally requires `DICEHUB_API_KEY`.
Resource and storage commands accept either `DICEHUB_API_KEY` or `DICEHUB_SESSION_COOKIE`.
Managed-key administration, `auth whoami`, top-level group creation, group move, and project move
use `DICEHUB_SESSION_COOKIE`. Never set both credential variables.

Current commands:

- `dicehub auth status`: verify API-key identity.
- `dicehub auth whoami`: local-development session bridge.
- `dicehub api-key list NAMESPACE_ID`: list managed-key metadata.
- `dicehub api-key get NAMESPACE_ID API_KEY_ID`: get one managed key.
- `dicehub api-key permissions NAMESPACE_ID`: list permissions assignable by the session.
- `dicehub api-key create NAMESPACE_ID --name NAME --permission PERMISSION --secret-fd FD`:
  create a key, optionally set `--not-before` and `--expires-at`, and deliver its one-time secret
  to an explicit descriptor.
- `dicehub api-key update NAMESPACE_ID API_KEY_ID --name NAME`: replace the name and optionally
  the complete permission set.
- `dicehub api-key revoke API_KEY_ID --yes`: permanently revoke one key.
- `dicehub group list`: list visible groups with bounded pagination and filters.
- `dicehub group get GROUP_ID`: resolve one group by immutable ID.
- `dicehub group get-by-route ROUTE`: resolve one group by exact route.
- `dicehub group create --name NAME --slug SLUG`: create a top-level group with a session; add
  `--parent-id GROUP_ID` to create a subgroup with an API key.
- `dicehub group update GROUP_ID`: update selected fields; slug/visibility changes need `--yes`.
- `dicehub group avatar set GROUP_ID SOURCE --yes`: replace an avatar from a bounded PNG file.
- `dicehub group avatar clear GROUP_ID --yes`: remove an avatar.
- `dicehub group roles GROUP_ID`: list assignable role IDs.
- `dicehub group members list-users GROUP_ID`: list user memberships.
- `dicehub group members list-teams GROUP_ID`: list team memberships.
- `dicehub group members add GROUP_ID MEMBER_ID --role-id ROLE_ID --yes`: add a direct member.
  Use `--group-route`, `--username` or `--team-route`, and `--role` for exact selectors.
- `dicehub group members update GROUP_ID MEMBER_ID --yes`: update a direct member.
- `dicehub group members remove GROUP_ID MEMBER_ID --yes`: remove a direct member.
- `dicehub group delete GROUP_ID --yes`: recursively delete a group subtree.
- `dicehub group move GROUP_ID TO_GROUP_ID --yes`: move a subgroup with a session.
- `dicehub app create PROJECT_ID --template-id TEMPLATE_ID --name NAME`: create an app.
- `dicehub app update APP_ID --name NAME`: update an app's name or description.
- `dicehub app delete APP_ID --yes`: recursively delete an app and its data.
- `dicehub app list PROJECT_ID`: list app metadata visible inside one project.
- `dicehub app get APP_ID`: resolve one app by immutable ID.
- `dicehub app get-by-route ROUTE`: resolve one app by exact route.
- `dicehub app roles APP_ID`: list assignable role IDs.
- `dicehub app members list-users APP_ID`: list user memberships.
- `dicehub app members list-teams APP_ID`: list team memberships.
- `dicehub app members add APP_ID MEMBER_ID --role-id ROLE_ID --yes`: add a direct member.
  Use `--app-route`, `--username` or `--team-route`, and `--role` for exact selectors.
- `dicehub app members update APP_ID MEMBER_ID --yes`: update a direct member.
- `dicehub app members remove APP_ID MEMBER_ID --yes`: remove a direct member.
- `dicehub config list APP_ID`: list configuration metadata visible inside one app.
- `dicehub config get CONFIG_ID`: resolve one configuration by immutable ID.
- `dicehub config create APP_ID`: create a configuration in one app.
- `dicehub config update CONFIG_ID`: update a configuration's name or description.
- `dicehub config delete CONFIG_ID --yes`: delete an entire non-default configuration.
- `dicehub config content list CONFIG_ID --area AREA`: list text or file entries.
- `dicehub config content get-text CONFIG_ID PATH`: read one UTF-8 text resource.
- `dicehub config content set-text CONFIG_ID PATH SOURCE`: replace text from a local file.
- `dicehub config content upload CONFIG_ID PATH SOURCE`: stream a local binary file.
- `dicehub config content download CONFIG_ID PATH DESTINATION`: stream a binary file locally.
- `dicehub config content delete CONFIG_ID PATH --area AREA --yes`: delete content permanently.
- `dicehub resource list NAMESPACE_ID`: list generic resource metadata below `data/`.
- `dicehub resource get RESOURCE_ID`: resolve one generic resource by immutable ID.
- `dicehub resource upload NAMESPACE_ID PATH SOURCE`: upload one local binary file.
- `dicehub resource download NAMESPACE_ID PATH DESTINATION`: download one binary file locally.
- `dicehub resource delete RESOURCE_ID --yes`: delete one generic resource by immutable ID.
- `dicehub project list`: list visible projects with bounded pagination and filters.
- `dicehub project get PROJECT_ID`: resolve one project by immutable ID.
- `dicehub project get-by-route ROUTE`: resolve one project by exact route.
- `dicehub project create --name NAME --slug SLUG`: create a project.
- `dicehub project update PROJECT_ID`: update selected fields; slug/visibility changes need `--yes`.
- `dicehub project roles PROJECT_ID`: list assignable role IDs.
- `dicehub project members list-users PROJECT_ID`: list user memberships.
- `dicehub project members list-teams PROJECT_ID`: list team memberships.
- `dicehub project members add PROJECT_ID MEMBER_ID --role-id ROLE_ID --yes`: add a direct member.
  Use `--project-route`, `--username` or `--team-route`, and `--role` for exact selectors.
- `dicehub project members update PROJECT_ID MEMBER_ID --yes`: update a direct member.
- `dicehub project members remove PROJECT_ID MEMBER_ID --yes`: remove a direct member.
- `dicehub project move PROJECT_ID TO_GROUP_ID --yes`: move a project subtree to a group.
- `dicehub project delete PROJECT_ID`: interactively confirm recursive project deletion; use
  `--yes` for non-interactive automation.
- `dicehub template list`: list server-catalog templates with bounded pagination and filters.
- `dicehub template get TEMPLATE_ID`: resolve one template by immutable ID.
- `dicehub template get-by-route ROUTE`: resolve one template by exact route.
- `dicehub run machine-types`: list machine hardware and net EUR machine-hour prices.
- `dicehub run list NAMESPACE_ID`: list permission-scoped run metadata.
- `dicehub run get RUN_ID`: get safe operational metadata for one run.
- `dicehub run status RUN_ID`: read one run-state snapshot without polling.
- `dicehub run wait RUN_ID --timeout SECONDS`: wait for one terminal state.
- `dicehub run watch RUN_ID --timeout SECONDS`: stream changed status snapshots as JSONL.
- `dicehub run download-results RUN_ID DESTINATION`: download a bounded result ZIP.
- `dicehub run start CONFIG_ID --machine-type ID --yes`: start a configuration run.
- `dicehub run stop RUN_ID --yes`: request interruption of one run.

### Managed API-key administration

API-key administration is intentionally session-only. Set `DICEHUB_SESSION_COOKIE` and do not set
`DICEHUB_API_KEY`; every `api-key` command rejects API-key authentication before sending a request.
The namespace and key IDs are positional so automation must name the exact management target.

Creation never writes a credential to stdout, stderr, JSON, text output, a regular file, or an
exception. Supply a writable pipe or socket descriptor numbered `3` or higher that does not alias
stdin, stdout, or stderr, and connect it directly to a trusted secret manager:

```bash
unset DICEHUB_API_KEY
export DICEHUB_URL=https://dicehub.com
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER

dicehub api-key create "$DICEHUB_NAMESPACE_ID" \
  --name "ci agent" \
  --permission VIEW_PROJECT_INFO \
  --permission VIEW_RUN_INFO \
  --expires-at "2026-09-16T12:00:00Z" \
  --secret-fd 3 \
  --output json \
  3> >(your-secret-manager write dicehub/ci-agent)
```

The CLI validates the descriptor type, writability, and separation from the standard streams before
creating the key. Terminals and regular files are rejected. It writes the raw secret plus one newline
with a complete-write loop and leaves the caller-owned descriptor open. Normal output contains
metadata only. If delivery fails after creation, the error identifies the new key ID so it can be
revoked; do not retry creation first.

`--not-before` and `--expires-at` accept ISO 8601 timestamps with an explicit timezone and
millisecond precision. Omit them for immediate activation and no expiration. The CLI validates
their order before it constructs a client; the server validates expiration against database time.

Update always requires the replacement name. Repeating `--permission` replaces the complete grant
set; omitting every `--permission` preserves the existing grants:

```bash
dicehub api-key list "$DICEHUB_NAMESPACE_ID" --output json
dicehub api-key permissions "$DICEHUB_NAMESPACE_ID" --output json
dicehub api-key update "$DICEHUB_NAMESPACE_ID" "$DICEHUB_API_KEY_ID" \
  --name "deployment agent" \
  --permission VIEW_PROJECT_INFO \
  --permission VIEW_RUN_INFO \
  --output json
dicehub api-key revoke "$DICEHUB_API_KEY_ID" --yes --output json
```

List, get, and update return server metadata including prefix, permissions, validity status,
activation, expiration, created, modified, and last-used timestamps. They never request or return
the secret. Revocation requires the exact immutable key ID and `--yes` before a client is
constructed. API-key mutations are never retried after an ambiguous result.

`api-key list` transparently walks newest-first server pages of 20 records and keeps its existing
JSON and text output. Every page retains the 64 KiB response limit. The command fails closed on
duplicate, out-of-order, oversized, or non-progressing pages, and refuses more than 10,000 keys or
501 requests. Deploy the matching paginated API before this CLI version; it deliberately does not
retry with the former unbounded list query.

Group automation uses independent managed-key grants inside the key's fixed scope:

- `VIEW_GROUP_INFO`: discover non-public metadata;
- `CREATE_SUBGROUP`: create a direct or descendant subgroup;
- `EDIT_GROUP_INFO`: edit metadata; avatar edits also need `VIEW_GROUP_INFO`;
- `DELETE_GROUP`: recursively delete an in-scope group;
- `VIEW_PUBLIC_GROUP_MEMBERS` and `VIEW_PRIVATE_GROUP_MEMBERS`: list visible memberships; and
- `MANAGE_GROUP_MEMBERS`: add, update, or remove direct user and team memberships.

High-impact mutations require `--yes`. No group mutation is retried after an ambiguous result:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub group list --parent-id 42 --output json
dicehub group get 73 --output json
dicehub group create --parent-id 73 --name Automation --slug automation --output json
dicehub group update 73 --description "Maintained by automation" --output json
dicehub group avatar set 73 ./avatar.png --yes --output json
dicehub group members list-users 73 --direct-only --output json
dicehub group members add 73 7 --role-id 3 --visibility private --yes --output json
dicehub group members add --group-route /research --username ada --role MEMBER --yes
dicehub group delete 74 --yes --output json
```

Top-level creation and move are session-only. Unset `DICEHUB_API_KEY`, set
`DICEHUB_SESSION_COOKIE`, and use the exact destination ID for a move:

```bash
dicehub group create --name Research --slug research --output json
dicehub group move 74 73 --yes --output json
```

Project reads, create, update, and delete require `DICEHUB_API_KEY`. Personal creation needs
`CREATE_USER_PROJECT`; group creation needs `CREATE_PROJECT`. Project-scoped keys cannot create
siblings. Update needs `EDIT_PROJECT_INFO`, and delete needs `DELETE_PROJECT`, within the key's
fixed scope. Project move is session-only and requires `DICEHUB_SESSION_COOKIE`.

Project member listing needs `VIEW_PUBLIC_PROJECT_MEMBERS` or `VIEW_PRIVATE_PROJECT_MEMBERS`.
Changes and target-scoped username lookup need `MANAGE_PROJECT_MEMBERS`; role lookup also needs
`VIEW_PROJECT_INFO`. Exact selector values are resolved first, and JSON output includes the
resolved IDs. The mutation still sends IDs only:

```bash
dicehub project members add \
  --project-route /ros/update_august \
  --team-route /research/solvers \
  --role DEVELOPER \
  --yes
```

App operations require `DICEHUB_API_KEY`. Managed keys need `VIEW_APP_INFO` for discovery,
`CREATE_APP` for creation, `EDIT_APP_INFO` for name or description changes, and `DELETE_APP` for
recursive deletion inside their fixed personal, group, or project scope. None of these grants
implies another:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub app list 42 --output json
dicehub app get 101 --output json
dicehub app create 42 --template-id 9 --name "Automated study" --output json
dicehub app update 101 --description "Updated by automation" --output json
dicehub app delete 101 --yes --output json
```

App member listing needs `VIEW_PUBLIC_APP_MEMBERS` or `VIEW_PRIVATE_APP_MEMBERS`. Changes and
target-scoped username lookup need `MANAGE_APP_MEMBERS`; role lookup also needs `VIEW_APP_INFO`.
The `--app-route` selector needs `VIEW_APP_INFO`, and `--team-route` needs `VIEW_TEAM_INFO`.
Exact selectors resolve before the ID-only mutation:

```bash
dicehub app members add \
  --app-route /ros/update_august/wind_tunnel \
  --username ada \
  --role EDITOR \
  --yes
```

Inherited memberships can be listed but not changed. App-member grants do not imply `SHARE_APP`,
configuration, run, or storage access. These commands require dicehub server `0.22.9` or newer.

App creation requires exact destination project and source template IDs. It is not idempotent. If
the CLI reports `MUTATION_OUTCOME_UNKNOWN`, do not replay it blindly; reconcile the exact project
or stop for manual cleanup.

Template discovery requires environment-only `DICEHUB_API_KEY` and returns metadata only.
Resolve an exact route before app creation when the deployment-specific numeric ID is unknown:

```bash
dicehub template list --type APP_TEMPLATE --tag openfoam --output json
dicehub template get-by-route /templates/openfoam_snappyhexmesh --output json
```

List filters are bounded and server-owned; repeated `--tag` values form an AND filter. Discovery
does not create an app, download template files, initialize user data, or execute returned content.
Treat names, routes, descriptions, paths, and tags as untrusted API metadata.

App update requires the exact immutable app ID and at least one change. If the CLI reports
`MUTATION_OUTCOME_UNKNOWN`, do not replay the mutation blindly; inspect that app ID first.

App deletion requires the exact immutable app ID and `--yes`; there is no interactive prompt.
Deletion includes configurations, runs, and stored app data. If the CLI reports
`MUTATION_OUTCOME_UNKNOWN`, the app may already be gone. Do not replay the mutation blindly;
reconcile that exact ID with an independently authorized API key.

Configuration operations require `DICEHUB_API_KEY`. Managed-key grants are independent:
`VIEW_CONFIG_INFO` discovers metadata, `CREATE_CONFIG` clones configurations, `EDIT_CONFIG_INFO`
changes names and descriptions, `DELETE_CONFIG` deletes whole non-default configurations,
`VIEW_CONFIG_CONTENT` reads text and files, and `EDIT_CONFIG_CONTENT` writes or deletes text and
files inside the fixed scope:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub config list 101 --output json
dicehub config get 301 --output json
dicehub config create 101 --name "Automated baseline" --output json
dicehub config update 301 --description "Maintained by automation" --output json
dicehub config delete 301 --yes --output json
dicehub config content list 301 --area texts --recursive --output json
dicehub config content set-text 301 solver/control.yaml ./control.yaml --output json
dicehub config content upload 301 mesh/mesh.bin ./mesh.bin --output json
dicehub config content download 301 mesh/mesh.bin ./downloaded-mesh.bin --output json
dicehub config content delete 301 solver/control.yaml --area texts --yes --output json
```

List/get return metadata only. Creation clones the app's default config unless
`--source-config-id` names an existing config in the same destination app. Text writes read UTF-8
from a local source file; content never needs to appear in a command argument. Downloads require an
explicit destination and refuse to overwrite unless `--overwrite` is supplied. Content deletion
requires the exact content area, relative path, and `--yes`.

Whole-config deletion is a separate top-level command. It requires the exact immutable config ID
and `--yes` before any client is constructed. The server refuses default-config deletion and
enforces the key's fixed scope. If the command reports `MUTATION_OUTCOME_UNKNOWN`, the config may
already be gone; reconcile that exact ID with an independently authorized identity and do not
replay the command blindly.

### Generic resources and storage

The singular `resource` command lists and resolves generic resources below the namespace `data/`
root. It also uploads and downloads binary files through the fixed storage route:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER

dicehub resource list "$DICEHUB_NAMESPACE_ID" \
  --path meshes --type file --recursive --limit 20 --output json
dicehub resource get "$DICEHUB_RESOURCE_ID" --output json
dicehub resource upload "$DICEHUB_NAMESPACE_ID" meshes/cube.stl ./cube.stl --output json
dicehub resource download \
  "$DICEHUB_NAMESPACE_ID" meshes/cube.stl ./downloaded-cube.stl --output json
dicehub resource delete "$DICEHUB_RESOURCE_ID" --yes --output json
```

`resource list` accepts `--path`, `--type`, `--recursive`, `--offset`, `--limit`, and `--cursor`.
The default path is the namespace data root. The default page size is 20 and the maximum is 50.
`--type` accepts `folder`, `text`, `file`, or `channel`. `resource upload` and `resource download`
accept `--max-bytes`; the default transfer limit is 2 GiB. Download refuses to overwrite an
existing local path unless `--overwrite` is supplied. The destination is always supplied by the
operator; the CLI never derives a local path from server data.

These commands accept exactly one of `DICEHUB_API_KEY` and `DICEHUB_SESSION_COOKIE`. The current
managed API-key catalog does not offer grants for generic resource metadata or storage transfers,
so use a session cookie for this feature today. Narrow grants require a server update. Keep credentials
in environment injection or a secret manager. Never put them in command arguments.

List and get return clean JSON model values in the `dicehub.cli/v1` envelope. Upload returns an
`upload` receipt with bytes and SHA-256 fields; download returns a `download` receipt with the
received byte count and SHA-256. Text output is tab-separated and terminal-safe. Resource deletion
requires the exact immutable resource ID and `--yes` before client construction. Upload and delete
are sent once. If a command reports `MUTATION_OUTCOME_UNKNOWN`, reconcile the exact operation
before retrying.

Run operations require environment-only `DICEHUB_API_KEY`. Managed keys need
`VIEW_RUN_INFO`, `DOWNLOAD_RUN_RESULT`, `START_RUN`, and `STOP_RUN` independently inside their fixed
scope:

The combined example below assumes one key was explicitly granted all four permissions. Separate
least-privilege keys can be used for metadata, download, start, and stop commands instead.

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub run list 42 --include-descendants --state running --output json
dicehub run get 12345678-1234-5678-9234-567812345678 --output json
dicehub run status 12345678-1234-5678-9234-567812345678 --output json
dicehub run wait 12345678-1234-5678-9234-567812345678 \
  --timeout 3600 --poll 2 --output json
dicehub run watch 12345678-1234-5678-9234-567812345678 \
  --timeout 3600 --poll 2 --output jsonl
dicehub run download-results \
  12345678-1234-5678-9234-567812345678 \
  ./run-results.zip \
  --output json
dicehub run start 301 --machine-type dh1_4x --nodes 1 --yes --output json
dicehub run stop 12345678-1234-5678-9234-567812345678 --yes --output json
```

List defaults to the exact namespace; `--include-descendants` is explicit. `--type` and `--state`
are repeatable. Status returns one snapshot under `data.run_status` and does not wait or poll.
Wait returns one successful terminal snapshot. It exits 4 with `RUN_FAILED` for `FAILED`,
`INTERRUPTED`, or `CANCELED`, and exits 6 with `RUN_TIMEOUT` when its finite deadline expires.

Watch writes one compact `dicehub.cli/v1` JSON object per line by default. It emits the first
snapshot and lifecycle-relevant changes only. A timestamp-only refresh is suppressed. The terminal
snapshot is emitted once. For a failed terminal state, one structured error line follows it and the
command exits 4. `--output text` provides tab-separated human output instead. Both commands require
`--timeout`; `--poll` defaults to 2 seconds, must be at least 0.1 seconds, and cannot exceed the
timeout. The maximum timeout is 7 days.

The metadata commands never request environment variables, user data, input/output data, creator
data, costs, app metadata, logs, results, reports, or storage credentials. Result download is a
separate bounded stream and requires its own grant. Its explicit destination is never derived from
server data, has a hard 2 GiB ceiling, and refuses to overwrite unless `--overwrite` is supplied.
The server omits `VTK/` entries, and a download before `FINISHED` may be empty or incomplete; the
command does not wait or poll. Start returns the same minimal status shape. `START_RUN` may consume
quota or incur charges and archives a configuration's prior terminal run as part of its
transactional replacement. `STOP_RUN` submits an asynchronous stop request; success does not claim
a terminal state. Managed API-key identities must omit `--notify`; it is available only when the
credential has a human notification recipient. Both CLI mutations require `--yes` before
constructing a client.

Run mutations are sent once and are never retried. On `MUTATION_OUTCOME_UNKNOWN`, reconcile the
exact configuration or run with an independently authorized identity before taking another action.
Legacy `VIEW_RUN` and `EDIT_RUN` remain broader and are not offered to new managed keys.

No configuration mutation is retried. On `MUTATION_OUTCOME_UNKNOWN`, inspect the exact config ID
and, for content operations, path using an independently authorized identity before deciding what
to do. A configuration creation, metadata change, content write, or deletion may already have
completed.

The immutable project ID is positional for get, update, move, and delete. This keeps destructive
automation reviewable. Route/visibility updates and move refuse to run without `--yes`. Project
deletion asks for `y` or `yes`, without case sensitivity, when standard input is an interactive
terminal and the prompt is visible on an interactive terminal. Redirected and non-interactive
calls must use `--yes`; moving changes descendant routes and inherited access:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER

dicehub project create \
  --name "Airfoil study" \
  --slug airfoil-study \
  --visibility private
dicehub project update 42 --description "Updated by automation"
dicehub project delete 42 --yes
```

Project move is the session-only exception:

```bash
unset DICEHUB_API_KEY
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
dicehub project move 42 73 --yes
```

For a scoped API-key update:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub project update 42 --description "Updated by automation"
```

For a scoped API-key deletion, pass the exact immutable project ID and explicit confirmation:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
dicehub project delete 42 --yes --output json
```

A project-scoped key can delete only its exact project and is revoked by that recursive deletion.
A personal- or group-scoped key can delete true descendant projects and remains active. Never
retry when the CLI reports `MUTATION_OUTCOME_UNKNOWN`; reconcile the exact ID first.

For API-key creation, omit `--group-id` for a personal-scoped key with `CREATE_USER_PROJECT`, or pass
the exact group ID for a group-scoped key with `CREATE_PROJECT`:

```bash
# Personal-scoped key:
dicehub project create --name "Agent project" --slug agent-project

# Group-scoped key:
dicehub project create --group-id 73 --name "Group project" --slug group-project
```

The server rejects a destination outside the key's fixed namespace scope.

Mutations are not idempotent. If the CLI reports `MUTATION_OUTCOME_UNKNOWN`, reconcile state before
doing anything else and never replay the command blindly. An ambiguous create may not return an ID;
use a unique name and slug, search only within the intended parent scope, and stop for manual
cleanup unless exactly one new project can be identified.
