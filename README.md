# dicehub Python

The dicehub Python SDK and CLI let you manage simulations on [dicehub](https://dicehub.com).
The project is available under the
[MIT license](https://github.com/dicehub/dicehub-python/blob/dev/LICENSE).

## Install

dicehub supports CPython 3.10 through 3.14.

```bash
pip install dicehub-python
```

The package provides the `dicehub` Python module and the `dicehub` command.

## Get started

Create a [dicehub account](https://dicehub.com/signup), then create an
[API key](https://dicehub.com/settings/tokens/create). A key with `VIEW_PROJECT_INFO` can list
your projects. Set the key in `DICEHUB_API_KEY` and run:

```python
import os

import dicehub

with dicehub.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
    for project in client.projects.list().projects:
        print(project.project_id, project.name)
```

The client connects to `https://dicehub.com` by default. Pass `base_url` when you use another
dicehub deployment.

The same API is available through `dicehub.AsyncClient`. See the
[async guide](https://github.com/dicehub/dicehub-python/blob/dev/docs/async.md).

## CLI

The CLI uses `DICEHUB_API_KEY` and connects to dicehub.com by default.

```bash
dicehub auth status
dicehub project list
dicehub run machine-types
```

Commands return JSON using the `dicehub.cli/v1` schema. See the
[CLI reference](https://github.com/dicehub/dicehub-python/blob/dev/docs/cli.md) for all commands and
options.

## Supported operations

The SDK covers authentication, API keys, groups, projects, apps, configurations, resources,
storage, runs, templates, users, and teams. The
[documentation](https://github.com/dicehub/dicehub-python/blob/dev/docs/index.md) lists the available
methods and the API-key permissions they need.

See the
[authentication guide](https://github.com/dicehub/dicehub-python/blob/dev/docs/authentication.md)
for session-only operations and the
[resources and storage guide](https://github.com/dicehub/dicehub-python/blob/dev/docs/resources.md)
for current permission and transfer limits. The
[getting-started guide](https://github.com/dicehub/dicehub-python/blob/dev/docs/getting-started.md)
explains the package-name change for users of the former private `dicehub` distribution. Release
history and deferred features are recorded in the
[changelog](https://github.com/dicehub/dicehub-python/blob/dev/CHANGELOG.md).

## Changes and costs

API-key permissions limit what a program can read or change. Starting a run can incur charges.
Deleting a resource can also delete its descendants. The SDK sends each mutation once; check the
current state before you repeat an operation whose result is unknown.

## Examples and development

Start with the
[authentication example](https://github.com/dicehub/dicehub-python/blob/dev/examples/auth_status.py),
the
[controlled cube workflow](https://github.com/dicehub/dicehub-python/blob/dev/docs/guides/controlled-cube-workflow.md),
or the
[car mesh workflow](https://github.com/dicehub/dicehub-python/blob/dev/examples/car_mesh/README.md).

Development instructions are in
[CONTRIBUTING.md](https://github.com/dicehub/dicehub-python/blob/dev/CONTRIBUTING.md). See the
[architecture](https://github.com/dicehub/dicehub-python/blob/dev/docs/development/architecture.md),
and [testing guide](https://github.com/dicehub/dicehub-python/blob/dev/docs/development/testing.md)
for development details.
