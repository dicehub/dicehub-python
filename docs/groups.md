---
title: Groups
description: Manage the complete dicehub group lifecycle through the typed SDK and CLI.
read_when:
  - Creating, listing, editing, moving, or deleting groups
  - Editing group avatars
  - Listing or managing group members
  - Granting group permissions to a managed API key
  - Adding group operations
---

# Groups

`client.groups` provides typed group lifecycle, avatar, role, and membership operations. Each
method sends one fixed GraphQL operation. External values are always GraphQL variables.

| Capability | SDK method | Managed API-key grant | Session-only |
| --- | --- | --- | --- |
| List groups and subgroups | `list()` | `VIEW_GROUP_INFO` for non-public data | No |
| Get by ID or route | `get()`, `get_by_route()` | `VIEW_GROUP_INFO` for non-public data | No |
| Create a top-level group | `create(parent_id=None)` | Not available | Yes |
| Create a subgroup | `create(parent_id=...)` | `CREATE_SUBGROUP` | No |
| Edit metadata | `update()` | `EDIT_GROUP_INFO` | No |
| Set or clear an avatar | `set_avatar()`, `clear_avatar()` | `VIEW_GROUP_INFO` and `EDIT_GROUP_INFO` | No |
| Delete a group subtree | `delete()` | `DELETE_GROUP` | No |
| Move a subgroup | `move()` | Not available | Yes |
| List or resolve assignable roles | `list_roles()`, `get_role_by_name()` | `VIEW_GROUP_INFO` | No |
| List user members | `list_user_members()` | `VIEW_PUBLIC_GROUP_MEMBERS` or `VIEW_PRIVATE_GROUP_MEMBERS` | No |
| List team members | `list_team_members()` | `VIEW_PUBLIC_GROUP_MEMBERS` or `VIEW_PRIVATE_GROUP_MEMBERS` | No |
| Add, edit, or remove a direct member | `add_member()`, `update_member()`, `remove_member()` | `MANAGE_GROUP_MEMBERS` | No |

The server checks every managed key against its immutable namespace scope. A group-scoped key can
act only on its group or permitted descendants. It cannot create a top-level sibling or move a
group to a new scope.

## Discover and edit

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    page = client.groups.list(parent_id=os.environ.get("DICEHUB_PARENT_GROUP_ID"))
    for group in page.groups:
        print(group.group_id, group.route, group.name)

    client.groups.update(
        group_id=os.environ["DICEHUB_GROUP_ID"],
        description="Maintained by automation",
    )
```

`list()` accepts `user_id`, `parent_id`, `search_filter`, `order_by`, `order`, `offset`, `limit`,
and `cursor`. `parent_id` selects direct child groups. `user_id` filters groups associated with
that user's memberships. Filters do not grant access.

Pages contain at most 50 records. Reuse a cursor only with the same filters and sort settings.
Supported sort fields are immutable group ID, name, created time, and updated time.

`update()` changes `name`, `slug`, `description`, and `visibility`. An empty description clears
it. At least one field is required. The CLI requires `--yes` for slug or visibility changes.

## Create and delete subgroups

Create a subgroup with a group-scoped managed key that has `CREATE_SUBGROUP`:

```python
with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    subgroup = client.groups.create(
        parent_id=os.environ["DICEHUB_PARENT_GROUP_ID"],
        name="Automation",
        slug="automation",
        description="Managed by the SDK",
        visibility=dh.GroupVisibility.PRIVATE,
    )
    print(subgroup.group_id)
```

`delete(group_id=...)` recursively deletes that group and its descendants. A managed key needs
`DELETE_GROUP` inside its fixed scope. Deleting a group can also delete projects, apps, configs,
runs, memberships, and managed keys below it. The CLI requires the exact group ID and `--yes`.

Top-level creation and subgroup move use session-cookie authentication:

```python
with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    session_cookie=os.environ["DICEHUB_SESSION_COOKIE"],
) as client:
    root = client.groups.create(name="Research", slug="research")
    client.groups.move(group_id=os.environ["DICEHUB_SUBGROUP_ID"], to_group_id=root.group_id)
```

The SDK rejects top-level creation and move before transport when the client uses an API key.

## Avatars

`set_avatar()` accepts a readable binary stream. The input must start with the PNG signature and
must not exceed 10 MiB. The SDK reads at most 10 MiB plus one byte before it sends the mutation.
`clear_avatar()` removes the stored avatar.

```python
from pathlib import Path

with Path(os.environ["DICEHUB_GROUP_AVATAR"]).open("rb") as source:
    client.groups.set_avatar(group_id=os.environ["DICEHUB_GROUP_ID"], source=source)

client.groups.clear_avatar(group_id=os.environ["DICEHUB_GROUP_ID"])
```

Avatar mutations need both `VIEW_GROUP_INFO` and `EDIT_GROUP_INFO`. The CLI requires `--yes` for
replacement and removal.

## Members and roles

Roles are deployment data. Resolve their immutable IDs instead of assuming fixed numbers:

```python
member_role = client.groups.get_role_by_name(
    group_id=os.environ["DICEHUB_GROUP_ID"],
    name="MEMBER",
)

users = client.groups.list_user_members(
    group_id=os.environ["DICEHUB_GROUP_ID"],
    include_inherited=True,
    deduplicate=False,
    limit=20,
)
teams = client.groups.list_team_members(group_id=os.environ["DICEHUB_GROUP_ID"])
```

Public and private membership visibility grants are independent. Request only the grant needed by
the automation. `include_inherited=False` returns direct memberships. `deduplicate=True` returns
one effective membership per user or team.

Member mutations use the user or team namespace ID as `member_id`:

```python
member_id = os.environ["DICEHUB_MEMBER_ID"]
group_id = os.environ["DICEHUB_GROUP_ID"]

client.groups.add_member(
    group_id=group_id,
    member_id=member_id,
    role_id=member_role.role_id,
    visibility=dh.MembershipVisibility.PRIVATE,
)
client.groups.update_member(
    group_id=group_id,
    member_id=member_id,
    visibility=dh.MembershipVisibility.PUBLIC,
)
client.groups.remove_member(group_id=group_id, member_id=member_id)
```

Only direct memberships can be changed. Managed API-key principals are protected from member
mutations. All member CLI mutations require `--yes` before client construction.

For an exact username or team route, resolve the selector before the ID-only mutation. See
[Membership selectors](memberships.md) for the sync, async, and CLI flows.

## CLI commands

```bash
dicehub group list --parent-id "$DICEHUB_PARENT_GROUP_ID" --output json
dicehub group get "$DICEHUB_GROUP_ID" --output json
dicehub group get-by-route "$DICEHUB_GROUP_ROUTE" --output json
dicehub group create --parent-id "$DICEHUB_PARENT_GROUP_ID" --name Automation --slug automation
dicehub group update "$DICEHUB_GROUP_ID" --description "Maintained by automation" --output json
dicehub group avatar set "$DICEHUB_GROUP_ID" ./avatar.png --yes
dicehub group avatar clear "$DICEHUB_GROUP_ID" --yes
dicehub group roles "$DICEHUB_GROUP_ID"
dicehub group members list-users "$DICEHUB_GROUP_ID" --direct-only
dicehub group members list-teams "$DICEHUB_GROUP_ID"
dicehub group members add "$DICEHUB_GROUP_ID" "$DICEHUB_MEMBER_ID" --role-id "$DICEHUB_ROLE_ID" --yes
dicehub group members add --group-route /research --username ada --role MEMBER --yes
dicehub group members update "$DICEHUB_GROUP_ID" "$DICEHUB_MEMBER_ID" --visibility public --yes
dicehub group members remove "$DICEHUB_GROUP_ID" "$DICEHUB_MEMBER_ID" --yes
dicehub group delete "$DICEHUB_GROUP_ID" --yes
```

For a top-level group or move, unset `DICEHUB_API_KEY` and set `DICEHUB_SESSION_COOKIE`:

```bash
dicehub group create --name Research --slug research
dicehub group move "$DICEHUB_SUBGROUP_ID" "$DICEHUB_TARGET_GROUP_ID" --yes
```

## Mutation safety

No group mutation is retried. A transport, HTTP, GraphQL, or malformed response failure raises
`MutationOutcomeUnknownError`. Reconcile the exact group or membership before you decide whether
to send another mutation. Creation, deletion, moves, and member changes can already have completed.

Treat names, routes, descriptions, cursors, and URLs as untrusted API data. The SDK stores them in
strict frozen Pydantic models. The CLI JSON-encodes them and escapes control characters in text
output. It never uses returned values as shell fragments or filesystem paths.

See the executable [`list_groups.py`](../examples/list_groups.py),
[`create_subgroup_with_api_key.py`](../examples/create_subgroup_with_api_key.py),
[`update_group_with_api_key.py`](../examples/update_group_with_api_key.py),
[`set_group_avatar_with_api_key.py`](../examples/set_group_avatar_with_api_key.py),
[`list_group_members.py`](../examples/list_group_members.py), and
[`delete_group_with_api_key.py`](../examples/delete_group_with_api_key.py) examples.
