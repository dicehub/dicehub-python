---
title: Membership selectors
description: Resolve exact human-readable selectors before ID-only group, project, and app mutations.
read_when:
  - Adding users or teams to groups, projects, or apps
  - Resolving usernames, team routes, or role names
  - Handling membership selector failures
---

# Membership selectors

Group, project, and app membership mutations use immutable IDs. The SDK also provides exact,
human-readable discovery methods so an operator does not need to find each ID first.

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

Use `client.groups.get_by_route()` and `client.groups.get_role_by_name()` for the same group flow.
Use `client.apps.get_by_route()` and `client.apps.get_role_by_name()` for an app. To add a team,
replace the user lookup with an exact canonical route:

```python
group = client.groups.get_by_route(route="/research")
role = client.groups.get_role_by_name(group_id=group.group_id, name="MEMBER")
team = client.teams.get_by_route(route="/research/solvers")
client.groups.add_member(
    group_id=group.group_id,
    member_id=team.team_id,
    role_id=role.role_id,
)
```

The async methods have the same parameters and return models. Add `await` to each lookup and
mutation.

## Exactness and scope

- Namespace and team selectors accept complete canonical routes. Display names and short slugs
  are not selectors. Team resolution also requires permission to view that exact team.
- Username matching is exact and case-insensitive. The server search remains scoped to principals
  that the caller can add to the target namespace. The SDK does not request a platform-wide user
  list, and the response model contains only the user ID and username.
- Role-name matching is exact, case-sensitive, and must identify one role in the target namespace.
- Zero username or role matches raise `SelectorResolutionError` with reason `NOT_FOUND`. Multiple
  exact matches raise it with reason `AMBIGUOUS`.
- Selector errors contain the selector kind, not the untrusted selector value.

Routes, usernames, and role names can change. Resolve them immediately before use. The final
`add_member()` request contains only the resolved namespace, member, and role IDs. Update and
remove operations remain ID-only.

## CLI

The existing ID form remains valid:

```bash
dicehub project members add 41 7 --role-id 3 --yes
```

Each selector axis accepts exactly one value. Human-readable examples are:

```bash
dicehub project members add \
  --project-route /ros/update_august \
  --username ada \
  --role DEVELOPER \
  --yes

dicehub group members add \
  --group-route /research \
  --team-route /research/solvers \
  --role MEMBER \
  --yes

dicehub app members add \
  --app-route /ros/update_august/wind_tunnel \
  --username ada \
  --role EDITOR \
  --yes
```

JSON output includes the resolved immutable IDs and the accepted selector metadata. Resolution
finishes before the CLI sends the mutation. `--yes` remains mandatory, and no selector failure
sends a membership mutation.

For group, project, and app `update_member()` calls, an omitted role or visibility stays unchanged;
at least one must be provided.

Group and project selectors require dicehub server `0.22.2` or newer. App membership selectors
require server `0.22.9` or newer.

See the executable
[`add_project_member_by_selectors.py`](../examples/add_project_member_by_selectors.py) and
[`add_app_member_by_selectors.py`](../examples/add_app_member_by_selectors.py) examples.
