---
title: Projects
description: Read and manage permission-scoped dicehub projects safely.
read_when:
  - Reading or changing projects through the SDK
  - Automating project lifecycle operations
  - Implementing a new vertical API domain
---

# Projects

## Read projects

API keys can list permission-scoped projects and resolve one project by immutable ID or route:

```python
import json

page = client.projects.list(
    group_id="42",
    search_filter="airfoil",
    limit=20,
)

for project in page.projects:
    print(json.dumps(project.model_dump(mode="json"), ensure_ascii=True))

project = client.projects.get(project_id="42")
same_project = client.projects.get_by_route(route=project.route)
assert same_project.project_id == project.project_id
```

`list()` accepts `user_id`, `group_id`, `search_filter`, `order_by`, `order`, `offset`, `limit`, and
`cursor`. The result includes a bounded page of summary fields plus `offset`, `count`, and an opaque
cursor. Use the returned cursor with the desired offset for subsequent requests. Page size is
limited to 50 to preserve the client's response-size boundary.

`user_id` filters projects associated with that user's memberships. `group_id` filters direct
children of that group; neither filter grants access.

Project discovery is permission-scoped by the server. A group filter narrows results; it never
grants access. Public projects may remain visible to keys without a project-view grant.

## Change projects

An authenticated browser session can perform the full project lifecycle:

```python
import os

from dicehub import Client, ProjectVisibility

with Client(
    base_url="http://127.0.0.1:8080",
    session_cookie=os.environ["DICEHUB_SESSION_COOKIE"],
) as client:
    created = client.projects.create(
        name="Airfoil study",
        slug="airfoil-study",
        description="Automated project",
        visibility=ProjectVisibility.PRIVATE,
    )
    client.projects.update(
        project_id=created.project_id,
        description="Updated by automation",
    )
    client.projects.move(project_id=created.project_id, to_group_id="73")
    client.projects.delete(project_id=created.project_id)
```

`create()` accepts an optional `group_id`; without one, dicehub creates a personal project. It also
accepts a personal-scoped API key granted `CREATE_USER_PROJECT`, or a group-scoped key granted
`CREATE_PROJECT`, when the destination matches that fixed scope:

```python
import os

from dicehub import Client, ProjectVisibility

with Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    created = client.projects.create(
        name="Agent study",
        slug="agent-study",
        group_id=os.environ.get("DICEHUB_PROJECT_GROUP_ID"),
        visibility=ProjectVisibility.PRIVATE,
    )
```

Use only the form matching the key: omit `group_id` for a personal-scoped key, or pass the exact
group ID for a group-scoped key. A project-scoped key cannot create a sibling, and no key may
select a destination outside its fixed scope. The server enforces these boundaries.

`update()` rejects calls without a changed field. Pass an empty description to clear it. Avatar
uploads remain a separate future domain.

`update()` also accepts an API key with `EDIT_PROJECT_INFO` on the target project, directly or
through its fixed personal or group scope:

```python
import os

from dicehub import Client

with Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    client.projects.update(
        project_id="42",
        description="Updated by automation",
    )
```

The server remains authoritative: a key scoped to one project cannot update a sibling.

## Members and roles

Project memberships use strict project models and the same mutation rules as group memberships:

```python
project = client.projects.get_by_route(route="/ros/update_august")
user = client.users.resolve_membership_candidate(
    namespace_id=project.project_id,
    username="ada",
)
role = client.projects.get_role_by_name(
    project_id=project.project_id,
    name="DEVELOPER",
)
client.projects.add_member(
    project_id=project.project_id,
    member_id=user.user_id,
    role_id=role.role_id,
)
```

`list_user_members()` and `list_team_members()` return bounded typed pages. Only direct
memberships can be changed. `update_member()` and `remove_member()` require immutable IDs.
Human-readable discovery never changes the final ID-only mutation contract. See
[Membership selectors](memberships.md) for exact team routes, selector errors, async parity, and
CLI examples.

Role discovery needs `VIEW_PROJECT_INFO`. Membership listing uses
`VIEW_PUBLIC_PROJECT_MEMBERS` or `VIEW_PRIVATE_PROJECT_MEMBERS`. Add, update, remove, and the
target-scoped username lookup need `MANAGE_PROJECT_MEMBERS`.

`delete()` accepts an API key with `DELETE_PROJECT`, with strict scope boundaries:

- A project-scoped key can delete only that exact project. The project's recursive deletion also
  deletes and revokes the key.
- A personal- or group-scoped key can delete true descendant projects and remains active after
  doing so. It cannot delete its own user or group scope.
- Legacy, shared, malformed, or unmanaged credentials fail closed before destructive side effects.

Move remains session-only, even when a key has both project-create and project-delete grants. See
[`examples/create_project_with_api_key.py`](../examples/create_project_with_api_key.py),
[`examples/update_project_with_api_key.py`](../examples/update_project_with_api_key.py), and
[`examples/delete_project_with_api_key.py`](../examples/delete_project_with_api_key.py) for
executable operations using environment-provided credentials.

Move requires permission on both the project and destination group. Delete recursively removes the
project and its descendants. Always resolve and display the immutable project ID before deletion;
the CLI asks for interactive confirmation before deletion and accepts `--yes` for automation.
Non-interactive deletion requires `--yes`. Slug/visibility updates and move also require `--yes`.
The server rejects deletion while an app is running in the project subtree.

Project mutations do not yet have server-side idempotency. A lost or malformed mutation response
raises `MutationOutcomeUnknownError`: the operation might have completed. Do not retry blindly.
For update, move, and delete, reconcile by the immutable ID. Creation has an unavoidable edge case:
if its response is lost, the new ID and complete route may be unavailable. Use a unique name and
slug, then reconcile within the intended parent scope. If you cannot identify exactly one new
project, stop for manual cleanup; never repeat `create()` or delete a name-only match.

Treat project names, routes, and cursors as untrusted API data. JSON-encode them for machine output;
never execute them or use them directly as shell fragments or filesystem paths.

See [`examples/manage_projects.py`](../examples/manage_projects.py) for an API-key lifecycle with
exact-ID cleanup. Its personal-scoped key needs `CREATE_USER_PROJECT`, `VIEW_PROJECT_INFO`,
`EDIT_PROJECT_INFO`, and `DELETE_PROJECT`.

The API-key detail smoke is read-only and needs the immutable ID of a project visible to that key:

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_PROJECT_ID=42
pytest tests/integration/test_live.py -k api_key_project_detail
```

The live lifecycle test is destructive and requires two explicit opt-ins:

```bash
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_PROJECT_MUTATION_TEST=1
pytest tests/integration/test_live.py -k project_lifecycle
```

Once creation returns an immutable ID, the test deletes only that exact project. An ambiguous
create or delete can leave the uniquely marked private project for manual reconciliation. The test
does not exercise move because it must not assume a disposable destination group.

The project-scoped API-key lifecycle creates two private projects and one temporary key, updates
only the target through both the SDK and CLI, proves the sibling remains unchanged, revokes the
key, and verifies subsequent authentication fails:

```bash
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_PROJECT_API_KEY_UPDATE_TEST=1
pytest tests/integration/test_live_project_api_key_update.py
```

This test deletes the key before deleting the two exact project IDs. As with every non-idempotent
mutation test, an interrupted or unknown outcome can require manual reconciliation by its unique
`dicehub-python-key-` marker.

The project-scoped API-key deletion lifecycle creates two disposable targets and one control
project, denies an out-of-scope deletion, deletes each exact target through the SDK and CLI, and
verifies that each project-scoped key is revoked with its target:

```bash
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_PROJECT_API_KEY_DELETE_TEST=1
pytest tests/integration/test_live_project_api_key_delete.py
```

The test never retries an ambiguous deletion. If it reports an unknown outcome, reconcile the
exact immutable project ID manually; cleanup deliberately skips that ID to avoid a destructive
replay.

The personal-scoped API-key creation lifecycle creates projects through both the SDK and CLI,
proves that supplying `group_id` is rejected, verifies exact IDs through a session, revokes the key,
and deletes only those IDs:

```bash
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_PROJECT_API_KEY_CREATE_TEST=1
pytest tests/integration/test_live_project_api_key_create.py
```

If either non-idempotent creation returns an ambiguous result, stop and reconcile the unique
`dicehub-python-key-create-` marker inside the personal namespace. The test never retries creation
or deletes a project found only by name.
