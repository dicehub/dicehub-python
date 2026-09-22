---
title: dicehub Python documentation
description: Documentation map for the dicehub Python SDK, CLI, and automation interfaces.
read_when:
  - Starting work in dicehub-python
  - Looking for SDK, CLI, testing, or release documentation
---

# dicehub Python documentation

The `dicehub` package provides typed synchronous and asynchronous Python clients and a deterministic
CLI for automation.

## Use the SDK

- [Getting started](getting-started.md)
- [Asynchronous SDK](async.md)
- [Hosted onboarding decision](decisions/0001-public-onboarding.md)
- [Authentication](authentication.md)
- [Managed API keys](api-keys.md)
- [Authentication check example](../examples/auth_status.py)
- [Async authentication check example](../examples/async_auth_status.py)
- [Managed API-key lifecycle example](../examples/manage_api_keys.py)
- [Controlled cube end-to-end example](guides/controlled-cube-workflow.md)
- [OpenFOAM 14 Case Run example](guides/openfoam-case-run.md)
- [Wildkatze Case Run example](guides/wildkatze-case-run.md)
- [Car mesh example](../examples/car_mesh/README.md)
- [Templates](templates.md)
- [Apps](apps.md)
- [Configurations](configs.md)
- [Resources and storage](resources.md)
- [Groups](groups.md)
- [Projects](projects.md)
- [Membership selectors](memberships.md)
- [Runs](runs.md)
- [API-key project creation example](../examples/create_project_with_api_key.py)
- [API-key project update example](../examples/update_project_with_api_key.py)
- [API-key project deletion example](../examples/delete_project_with_api_key.py)
- [API-key app creation example](../examples/create_app_with_api_key.py)
- [API-key app update example](../examples/update_app_with_api_key.py)
- [API-key app deletion example](../examples/delete_app_with_api_key.py)
- [App discovery example](../examples/list_apps.py)
- [Template discovery example](../examples/list_templates.py)
- [Configuration discovery example](../examples/list_configs.py)
- [Run discovery example](../examples/list_runs.py)
- [Machine type discovery example](../examples/list_machine_types.py)
- [Run result download example](../examples/download_run_results.py)
- [Run start example](../examples/start_run.py)
- [Run stop example](../examples/stop_run.py)
- [Run wait example](../examples/wait_for_run.py)
- [Group discovery example](../examples/list_groups.py)
- [API-key group update example](../examples/update_group_with_api_key.py)
- [API-key subgroup creation example](../examples/create_subgroup_with_api_key.py)
- [API-key group deletion example](../examples/delete_group_with_api_key.py)
- [API-key group avatar example](../examples/set_group_avatar_with_api_key.py)
- [Group membership discovery example](../examples/list_group_members.py)
- [Project membership selector example](../examples/add_project_member_by_selectors.py)
- [App membership selector example](../examples/add_app_member_by_selectors.py)
- [API-key configuration creation example](../examples/create_config_with_api_key.py)
- [API-key configuration deletion example](../examples/delete_config_with_api_key.py)
- [API-key configuration metadata update example](../examples/update_config_with_api_key.py)
- [API-key configuration content editing example](../examples/edit_config_content_with_api_key.py)
- [API-key YAML value batch update example](../examples/set_config_values_with_api_key.py)
- [CLI](cli.md)
- [Errors](errors.md)

## Develop the SDK

- [Architecture](development/architecture.md)
- [Testing](development/testing.md)
- [Managed API-key live test](guides/managed-api-keys.md)

All pages are plain Markdown with YAML frontmatter so they can later be consumed by the dicehub
Astro documentation site without changing their content model.
