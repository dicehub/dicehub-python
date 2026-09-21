---
title: Configurations
description: Discover, create, import geometry, edit, and delete configurations with the typed SDK.
read_when:
  - Listing or resolving configurations
  - Creating, editing, or deleting configuration metadata, text, or files
  - Importing STL geometry through the fixed server converter
  - Granting configuration permissions to an API key
  - Adding configuration operations
---

# Configurations

`client.configs` provides fixed operations for configuration automation:

- `list()` and `get()` read configuration metadata;
- `create()` clones the app's default configuration or an explicit same-app source;
- `update()` changes a configuration's name or description;
- `delete()` permanently removes one complete non-default configuration;
- `import_geometry()` starts the server-owned conversion and optional first-import domain setup;
- `list_content()`, `get_text()`, `set_text()`, `set_values()`, and `delete_content()` manage text
  resources; and
- `upload_file()` and `download_file()` stream binary files.

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    page = client.configs.list(app_id=os.environ["DICEHUB_APP_ID"])
    for config in page.configs:
        print(config.config_id, config.name, config.is_default)

    client.configs.update(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        description="Maintained by automation",
    )
```

The matching CLI commands are:

```bash
dicehub config list "$DICEHUB_APP_ID" --output json
dicehub config get "$DICEHUB_CONFIG_ID" --output json
dicehub config create "$DICEHUB_APP_ID" --name "Automated baseline" --output json
dicehub config update "$DICEHUB_CONFIG_ID" --description "Maintained by automation"
dicehub config delete "$DICEHUB_CONFIG_ID" --yes --output json
```

`config delete` removes the whole configuration and all associated content. It is intentionally
separate from `config content delete`, which removes only one content path or subtree.

## Batch YAML value updates

`set_values()` changes one or more scalar values in an existing `.yaml` text resource with one
mutation:

```python
client.configs.set_values(
    config_id=os.environ["DICEHUB_CONFIG_ID"],
    path="solver/control.yaml",
    updates=(
        dh.ConfigValueUpdate(path=("controlDict", "endTime"), value=200),
        dh.ConfigValueUpdate(path=("controlDict", "writeInterval"), value=20),
        dh.ConfigValueUpdate(path=("controlDict", "writeAscii"), value=True),
    ),
)
```

This operation is SDK-only in v1; there is no matching CLI command. Connected app and editor
clients receive one incremental collaboration update for the complete batch.

Each YAML value path has 1 to 64 non-empty printable UTF-8 segments, each no longer than 255
characters. The UTF-8 encoding of all segments plus separators is limited to 1024 bytes. Segments
are sent as a list, so a YAML key may contain `/`. A batch has 1 to 100 unique paths. Values are
limited to UTF-8 strings, integers, finite floats, booleans, or `None`; mappings and sequences are
rejected before HTTP. The complete serialized batch is limited to 2 MiB.

The server checks the full batch before it changes the document. All intermediate mapping keys and
sequence indexes must exist. The final path segment may create a mapping key, but it cannot append
to a sequence or replace a mapping or sequence. If one update is invalid, none of the updates are
applied. Update an anchored scalar instead of an alias target. Flow-sequence items with anchors or
tags are not supported. An implicit-null sequence item must belong to a root block sequence or a
block sequence stored directly under a mapping key. Documents and replacement strings with
characters outside the Unicode Basic Multilingual Plane are rejected because Python and JavaScript
use different collaboration offset units. The API key needs `EDIT_CONFIG_CONTENT` in the
configuration's scope.

The mutation returns `None` on success and is never retried. If the outcome is unknown, reconcile
the exact YAML resource and value paths before deciding what to do.

## Text and file content

Configuration content is divided into two explicit areas:

- `ConfigContentArea.TEXTS` contains UTF-8 text resources; and
- `ConfigContentArea.FILES` contains opaque binary files.

The two areas can use the same relative path without colliding. Listing returns typed entries and
can be shallow or recursive:

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    page = client.configs.list_content(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        area=dh.ConfigContentArea.TEXTS,
        recursive=True,
        limit=50,
    )
    for entry in page.entries:
        print(entry.path, entry.resource_type.value)

    client.configs.set_text(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        path="solver/control.yaml",
        content="iterations: 200\n",
    )
```

Binary transfers stream through file objects instead of loading the full object into memory:

```python
from pathlib import Path

with Path("mesh.bin").open("rb") as source:
    client.configs.upload_file(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        path="mesh/mesh.bin",
        source=source,
    )

with Path("downloaded-mesh.bin").open("xb") as destination:
    byte_count = client.configs.download_file(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        path="mesh/mesh.bin",
        destination=destination,
    )
```

The SDK limits text to 2 MiB and each binary transfer to 2 GiB by default. Callers may set a lower
`max_bytes` for binary transfers. A failed SDK download can leave partial bytes in a caller-provided
destination; use a temporary file and atomic rename when replacing durable data. The CLI does this
automatically for `--overwrite` and removes a newly created partial destination after failure.

The matching CLI surface is intentionally explicit about the content area and local paths:

```bash
dicehub config content list "$DICEHUB_CONFIG_ID" --area texts --recursive
dicehub config content get-text "$DICEHUB_CONFIG_ID" solver/control.yaml
dicehub config content set-text "$DICEHUB_CONFIG_ID" solver/control.yaml ./control.yaml
dicehub config content upload "$DICEHUB_CONFIG_ID" mesh/mesh.bin ./mesh.bin
dicehub config content download \
  "$DICEHUB_CONFIG_ID" mesh/mesh.bin ./downloaded-mesh.bin
dicehub config content delete \
  "$DICEHUB_CONFIG_ID" solver/control.yaml --area texts --yes
```

Text is read from a local UTF-8 file for `set-text`; it is never accepted as a command argument.
Downloads require an explicit destination and refuse to overwrite it unless `--overwrite` is set.
Content deletion is permanent, accepts files or subtrees, and requires `--yes`.

## Authorization boundary

A project-scoped key reaches configurations in apps inside that project only. A group-scoped key
inherits its grants into descendant projects and their apps. A personal-scoped key reaches projects
and apps directly below the personal namespace; it does not inherit group memberships held by the
human owner.

The grants are deliberately independent:

| Permission | Allows | Does not imply |
| --- | --- | --- |
| `VIEW_CONFIG_INFO` | List and read configuration metadata | Content reads or writes |
| `CREATE_CONFIG` | Clone a configuration in an allowed app | Later discovery or editing |
| `EDIT_CONFIG_INFO` | Change name or description | Metadata discovery or content writes |
| `DELETE_CONFIG` | Delete one complete non-default configuration | Metadata/content discovery or path editing |
| `VIEW_CONFIG_CONTENT` | List content, read text, download files | Metadata discovery or writes |
| `EDIT_CONFIG_CONTENT` | Set/delete text and upload/delete files | Reads or metadata changes |

`VIEW_CONFIG_INFO` returns metadata such as immutable IDs, name, description, default status,
template version, and update state. It does not grant `VIEW_APP_INFO`, configuration file content,
resource reads, run access, storage access, creation, editing, or deletion.

`CREATE_CONFIG` permits one non-idempotent clone operation in apps covered by the key's fixed
personal, group, or project scope. It does not imply `VIEW_CONFIG_INFO`: a narrow creator can use
the returned config metadata but cannot list or fetch configurations later. If
`source_config_id` is omitted, dicehub clones the destination app's default configuration. An
explicit source ID must belong to that same app; cross-app cloning fails before quota or data
changes.

`DELETE_CONFIG` permits permanent deletion only for configurations in apps covered by the key's
fixed personal, group, or project scope. It does not imply metadata or content discovery, and the
server refuses deletion of an app's default configuration. The SDK requires the exact immutable
config ID; the CLI additionally requires `--yes` before constructing a client.

Existing broad `VIEW_APP` roles remain server-compatible with metadata and content reads. Existing
broad `EDIT_APP` roles remain compatible with creation, metadata changes, content writes, and
whole-config deletion. Managed-key creation exposes the narrow grants instead.

Creation sends exactly one request. If the SDK or CLI reports `MUTATION_OUTCOME_UNKNOWN`, the
configuration may exist. Do not retry blindly; reconcile the destination app using an independently
authorized read identity and a unique requested name.

Metadata updates, text writes, binary uploads, content deletion, and whole-config deletion are also
mutations and are never retried automatically. On `MUTATION_OUTCOME_UNKNOWN`, inspect the exact
config ID and, for content operations, path with an independently authorized identity before
deciding what to do. A binary upload may have completed; a whole configuration may already be gone.

## Path and transport safety

All content operations take a configuration ID plus a relative path. Paths cannot be absolute, end
with `/`, contain `.` or `..` segments, empty segments, backslashes, control characters, or segments
longer than 255 characters. The complete path is limited to 1024 characters. The server derives the
storage location from the authorized configuration; clients cannot submit a bucket, app route, or
arbitrary object-store key.

GraphQL carries metadata and UTF-8 text. Binary files use fixed-origin authenticated REST routes.
The transport preserves TLS verification, refuses redirects, ignores proxy environment variables,
rejects encoded responses, bounds response sizes, and never includes server bodies in public
exceptions. Treat every returned path, name, description, text value, and cursor as untrusted data.

## Pagination and untrusted data

`list()` defaults to 20 records and accepts `search_filter`, `order`, `offset`, `limit`, and
`cursor`. Results sort by immutable config ID because that is the server's only supported config
sort field. Limits are validated before HTTP and capped at 50.

The SDK returns immutable, strict Pydantic models and never evaluates API values as shell commands
or filesystem paths.

## Import STL geometry

The first import slice is deliberately restricted to an app created from the trusted
`openfoam_snappyhexmesh` template whose `application.yaml` declares
`metadata.application: snappyHexMesh`. Upload one non-empty normalized STL basename to that
template's geometry location, then ask dicehub to run its fixed converter:

```python
import os
from pathlib import Path

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    with Path("cube.stl").open("rb") as source:
        client.configs.upload_file(
            config_id=os.environ["DICEHUB_CONFIG_ID"],
            path="case/constant/triSurface/cube.stl",
            source=source,
        )

    import_runs = client.configs.import_geometry(
        config_id=os.environ["DICEHUB_CONFIG_ID"],
        filename="cube.stl",
    )
    print(import_runs.conversion_run.run_id, import_runs.conversion_run.state.value)
    if import_runs.setup_run is not None:
        print(import_runs.setup_run.run_id, import_runs.setup_run.state.value)
```

`import_geometry()` accepts only a bare ASCII `.stl` filename normalized like the web uploader. The
client cannot choose a module, flow, environment, storage mapping, queue, or batch. The server owns
those details and returns `GeometryImportRuns`: the required conversion run snapshot and an optional
setup run snapshot. Other app templates and mismatched application metadata fail with
`BAD_PARAMETERS`. A missing or empty source upload fails with `NOT_FOUND_ERROR`. The operation does
not provide a generic converter for arbitrary configurations.

For the first geometry in a fresh snappyHexMesh configuration, dicehub creates a private ordered
queue. The `convert_stl` stage writes the normalized surface, geometry YAML, and renderable VTP.
Only a successful conversion starts `setup_bounding_box`, which writes the background mesh,
material point, and configuration camera settings. Poll `conversion_run` to `FINISHED`, then poll
the non-null `setup_run` to `FINISHED` before reading those generated resources.

For a later geometry import, `setup_run` is `None`. This is deliberate: dicehub converts the new
surface but does not replace a domain, material point, or camera that the caller can already have
tuned. The decision uses existing geometry content in the configuration; callers cannot force or
skip setup through mutation arguments.

The operation needs `EDIT_CONFIG_CONTENT` for the target configuration and `START_RUN` for its
server-owned runs. Poll each returned UUID with an independently granted `VIEW_RUN_INFO`.

The mutation is sent once and never retried. `MUTATION_OUTCOME_UNKNOWN` means one or both runs can
exist; reconcile the exact configuration's run history before retrying or deleting its project. A
successful response without `conversion_run` is also unknown. A null `setup_run` is a valid later
import result.

## Local end-to-end test

The mutating lifecycle test creates temporary target and control projects, apps, a configuration,
and a project-scoped key. It exercises SDK and CLI metadata/text/file operations, verifies sibling
denial and revocation, then removes only the exact IDs it created:

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_CONFIG_API_KEY_EDIT_TEST=1
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
pytest tests/integration/test_live_config_api_key_edit.py -vv
```

Do not enable the mutation opt-in against shared or production data. If an ambiguous setup or
cleanup outcome is reported, reconcile the exact IDs from the failure before running the test
again.

The deletion lifecycle creates target and sibling configurations, uses a project-scoped
`DELETE_CONFIG` key through both SDK and CLI, proves sibling and default-config denial, verifies
revocation, and cleans up only exact temporary project IDs:

```bash
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_CONFIG_API_KEY_DELETE_TEST=1
export DICEHUB_URL=http://127.0.0.1:8080
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER
pytest tests/integration/test_live_config_api_key_delete.py -vv
```
