---
title: Apps
description: Discover, manage, and share app access through the typed dicehub SDK and CLI.
read_when:
  - Listing or resolving apps
  - Granting VIEW_APP_INFO, CREATE_APP, EDIT_APP_INFO, or DELETE_APP to an API key
  - Creating apps, updating app metadata, or deleting app subtrees
  - Listing roles or managing direct app memberships
  - Adding app operations
---

# Apps

`client.apps` provides fixed GraphQL operations for app discovery and lifecycle mutations:

- `list(project_id=...)` lists apps visible inside one exact project;
- `get(app_id=...)` resolves an immutable app ID;
- `get_by_route(route=...)` resolves an exact app route;
- `list_roles(app_id=...)` lists roles assignable in one app;
- `list_user_members(...)` and `list_team_members(...)` return direct or inherited memberships;
- `add_member(...)`, `update_member(...)`, and `remove_member(...)` manage one direct membership;
- `create(project_id=..., template_id=..., name=...)` creates an app from a template; and
- `update(app_id=..., name=..., description=...)` updates selected metadata; and
- `delete(app_id=...)` recursively deletes an app and its data.

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    page = client.apps.list(project_id=os.environ["DICEHUB_PROJECT_ID"])
    for app in page.apps:
        print(app.app_id, app.name, app.visibility)
```

The matching CLI commands are:

```bash
dicehub app list "$DICEHUB_PROJECT_ID" --output json
dicehub app get "$DICEHUB_APP_ID" --output json
dicehub app get-by-route "$DICEHUB_APP_ROUTE" --output json
dicehub app create "$DICEHUB_PROJECT_ID" \
  --template-id "$DICEHUB_TEMPLATE_ID" \
  --name "Automated study" \
  --description "Created by an agent" \
  --output json
dicehub app update "$DICEHUB_APP_ID" \
  --description "Updated by an agent" \
  --output json
dicehub app delete "$DICEHUB_APP_ID" --yes --output json
```

In Python, resolve a stable route when its deployment-specific ID is not already known:

```python
template = client.templates.get_by_route(route="/templates/openfoam_snappyhexmesh")
created = client.apps.create(
    project_id=os.environ["DICEHUB_PROJECT_ID"],
    template_id=template.template_id,
    name="Automated study",
)
```

## Authorization boundary

A managed API key needs `VIEW_APP_INFO`. A project-scoped key reaches apps in that project only. A
group-scoped key reaches apps in projects below that group, including subgroup projects. A
personal-scoped key reaches apps in projects directly below the personal namespace; it does not
inherit group memberships held by the human owner.

`VIEW_APP_INFO` exposes app metadata only. It does not authorize app creation, editing, deletion,
configuration content, runs, storage, or registry operations. Public apps retain their normal
visibility baseline, while private and internal apps require an in-scope grant.

## Creation boundary

A managed API key needs `CREATE_APP`. A project-scoped key creates only inside its exact project. A
group-scoped key creates inside projects below the group, including subgroup projects. A
personal-scoped key creates inside projects below the personal namespace and does not inherit the
human owner's group memberships.

Both `project_id` and `template_id` are mandatory in the SDK and CLI. The server never selects the
human owner's default project for an API key. `CREATE_APP` does not imply `VIEW_PROJECT_INFO` or
`VIEW_APP_INFO`; grant discovery separately when the automation needs it. The source template must
still be visible to the key under the server's existing template rules.

When the deployment-specific numeric ID is unknown, resolve a stable route first through
`client.templates.get_by_route()` or `dicehub template get-by-route`, and pass the returned
immutable `template_id` into the separate create operation. Missing or inaccessible routes raise a
typed dicehub error. Discovery never hides or retries app creation.

App creation is not idempotent. A lost, malformed, or otherwise untrustworthy response raises
`MutationOutcomeUnknownError`, with `retryable=false`. Do not replay the create blindly. Reconcile
within the exact destination project, or stop for manual cleanup when the created app ID is unknown.
The SDK never automatically retries the mutation.

## Membership boundary

App member listing uses grants separate from app metadata and mutations:

- `VIEW_PUBLIC_APP_MEMBERS` lists public memberships;
- `VIEW_PRIVATE_APP_MEMBERS` lists private memberships; and
- `MANAGE_APP_MEMBERS` adds, updates, or removes direct user and team memberships.

These permissions inherit from the key's fixed user, group, or project scope. They do not imply
`VIEW_APP_INFO`, `SHARE_APP`, configuration access, run access, or storage access. Role discovery
needs `VIEW_APP_INFO`. Target-scoped username discovery and membership mutations need
`MANAGE_APP_MEMBERS`. Resolving `--app-route` needs `VIEW_APP_INFO`; resolving `--team-route`
also needs `VIEW_TEAM_INFO`.

Lists include inherited access by default. Pass `include_inherited=False` for direct memberships
only. Team lists also support `deduplicate=True`. Inherited memberships are read-only; update and
remove accept an exact direct member ID and never select a row from a display name. In
`update_member()`, an omitted role or visibility stays unchanged; at least one must be provided.

```python
app = client.apps.get_by_route(route="/ros/update_august/wind_tunnel")
user = client.users.resolve_membership_candidate(
    namespace_id=app.app_id,
    username="ada",
)
role = client.apps.get_role_by_name(app_id=app.app_id, name="EDITOR")
client.apps.add_member(
    app_id=app.app_id,
    member_id=user.user_id,
    role_id=role.role_id,
)
```

The exact selector calls are separate reads. The final mutation sends IDs only. Add, update, and
remove are not retried after an ambiguous response. Reconcile the exact app and member IDs before
another mutation. Managed API-key principals and other server-owned memberships cannot be changed
through these methods.

Matching CLI commands are available under `dicehub app roles` and `dicehub app members`. Every
membership mutation requires `--yes`. App membership operations require dicehub server `0.22.9`
or newer. See [Membership selectors](memberships.md) for route and username rules.

The live lifecycle test needs a disposable source template and two explicit mutation opt-ins:

```bash
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_APP_TEMPLATE_ID=42
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_APP_MEMBERSHIP_TEST=1
pytest tests/integration/test_live_app_memberships.py
```

The test creates one private project and app. It removes its exact direct membership in `finally`
and then deletes the exact project ID.

## Metadata-update boundary

A managed API key needs `EDIT_APP_INFO` to change an app's name or description. A project-scoped
key reaches only apps in that exact project. Group-scoped keys inherit the grant into projects
below the group, including subgroup projects. Personal-scoped keys inherit it into projects below
the personal namespace, without inheriting the human owner's group memberships.

`EDIT_APP_INFO` is deliberately narrower than `EDIT_APP`: it does not authorize config or resource
writes, execution, runs, storage, registry pushes, moves, or deletion. It also does not imply
`VIEW_APP_INFO`; add that grant separately when automation must read app metadata.

Pass at least one of `name` or `description`. An empty description clears it; `None` leaves it
unchanged. Updates are not retried. If a response is lost or untrustworthy, the SDK raises
`MutationOutcomeUnknownError`; reconcile the exact immutable app ID before deciding what to do.

## Deletion boundary

A managed API key needs `DELETE_APP`. A project-scoped key deletes apps only in that exact project.
Group-scoped keys inherit the grant into projects below the group, including subgroup projects.
Personal-scoped keys inherit it into projects below the personal namespace, without inheriting the
human owner's group memberships.

Deletion recursively removes the app namespace and descendants, including configurations, runs,
and stored app data. Running apps retain the server's existing refusal. `DELETE_APP` does not imply
`VIEW_APP_INFO`, app creation, metadata editing, registry push, or run operations. `moveApp` remains
session-only. Deleting an app does not revoke the key because managed keys are scoped to a user,
group, or project rather than the app itself.

The CLI requires `--yes` and an exact immutable app ID. The SDK performs one mutation request and
never retries it. If a response is lost or untrustworthy, `MutationOutcomeUnknownError` means the
app may already be gone: inspect that exact ID with an independently authorized session before any
further action.

## Pagination and filtering

`list()` defaults to 20 records and accepts `search_filter`, `order_by`, `order`, `offset`, `limit`,
`cursor`, and `is_published`. Limits are validated before HTTP and capped at 50. Pass
`is_published=True` or `False` for an explicit publication filter; the default `None` includes both.

Project IDs, app IDs, routes, names, descriptions, and cursor values are untrusted API data. The
SDK returns them as immutable Pydantic models and never evaluates them as shell or filesystem input.
