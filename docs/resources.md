---
title: Resources and storage
description: List, inspect, delete, upload, and download generic namespace resources.
read_when:
  - Listing generic namespace resources
  - Uploading or downloading data files
  - Deleting a resource by immutable ID
  - Choosing API-key or session authentication for storage
---

# Resources and storage

The `client.resources` service provides metadata operations for the generic namespace `data/`
tree. The separate `client.storage` service transfers binary objects in that tree. The services
use fixed dicehub operations and do not return signed URLs or accept arbitrary URLs.

## Resource metadata

`ResourceType` has four values: `FOLDER`, `TEXT`, `FILE`, and `CHANNEL`. Resource keys returned by
the server include the `data/` prefix. Method arguments use a relative path below that prefix.

List one namespace with bounded pagination:

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    session_cookie=os.environ["DICEHUB_SESSION_COOKIE"],
) as client:
    page = client.resources.list(
        namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
        path="meshes",
        resource_type=dh.ResourceType.FILE,
        recursive=True,
        limit=20,
    )
    for resource in page.resources:
        print(resource.resource_id, resource.key, resource.resource_type.value)
```

`list()` defaults to the namespace data root, a shallow result, offset `0`, and 20 records. The
maximum page size is 50. `cursor` continues a server page. `offset`, `limit`, and `cursor` are
validated before a request. A page is a strict immutable `ResourcePage` model.

Resolve or delete one exact immutable resource ID:

```python
resource = client.resources.get(
    resource_id=os.environ["DICEHUB_RESOURCE_ID"],
)
print(resource.model_dump(mode="json"))

client.resources.delete(
    resource_id=os.environ["DICEHUB_RESOURCE_ID"],
)
```

`get()` returns a strict immutable `Resource`. `delete()` removes the exact resource ID. Deleting
a folder also removes its resource subtree under the current server contract. The method does not
accept a path, and it does not retry after an ambiguous network result. Reconcile that ID before
sending another mutation if the client reports `MUTATION_OUTCOME_UNKNOWN`.

## Text resources

Text methods use UTF-8 and a 2 MiB content limit:

```python
client.resources.create_text(
    namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
    path="notes/agent.yaml",
    content="enabled: true\n",
)

text_resource = client.resources.get_by_key(
    namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
    path="notes/agent.yaml",
)
content = client.resources.get_text(resource_id=text_resource.resource_id)

client.resources.set_text(
    resource_id=text_resource.resource_id,
    content=content.replace("true", "false"),
)
```

`create_text()` uses an exact namespace and relative path. It replaces an existing resource at
that path and can create a new resource ID. Use `set_text()` to replace the content of one exact
existing text resource. `get_text()` and `set_text()` use an exact immutable resource ID. Writes
normalize CRLF line endings to LF. The SDK sends each text mutation once and reports an ambiguous
result as `MUTATION_OUTCOME_UNKNOWN`.

## Binary storage

Storage methods take local paths. They stream data in bounded chunks and return strict immutable
receipts:

```python
from pathlib import Path

upload = client.storage.upload_file(
    namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
    path="meshes/cube.stl",
    source_path=Path("./cube.stl"),
)
print(upload.model_dump(mode="json"))

download = client.storage.download_file(
    namespace_id=os.environ["DICEHUB_NAMESPACE_ID"],
    path="meshes/cube.stl",
    destination_path=Path("./downloaded-cube.stl"),
)
print(download.model_dump(mode="json"))
```

The async service keeps the same paths and `BinaryIO` arguments. Network streaming is native async;
local file and stream operations run in worker threads. Caller-owned streams remain open.

`upload_file()` returns `UploadReceipt` with `namespace_id`, `path`, `bytes_sent`, `sha256`, and
`server_verified`. `download_file()` returns `DownloadReceipt` with `namespace_id`, `path`,
`bytes_received`, `sha256`, and `server_verified`. Use `model_dump(mode="json")` when a receipt
must cross a JSON boundary. The SDK does not expose credentials or an object-store URL.

Each transfer defaults to a 2 GiB limit. Pass a lower `max_bytes` for a stricter operation limit.
The client rejects an upload or download that exceeds that limit. The server may enforce a lower
limit as well. A download refuses to replace an existing destination unless `overwrite=True` is
explicit. Replacement uses a temporary sibling and an atomic rename after the transfer succeeds.
An interrupted or invalid transfer does not replace an existing destination.

The SDK sends each upload and deletion once. It does not retry a mutation after a timeout or other
ambiguous result. A successful upload receipt contains the locally counted bytes and SHA-256. The
current server does not return an independent SHA-256 confirmation, so `server_verified` is
`False`. Treat the receipt hash as a local measurement only. Backend issue #3353 tracks a
server-confirmed integrity contract.

An upload replaces any resource at the same namespace path. The current server has no conditional
write or no-clobber option. Reconcile the path after `MUTATION_OUTCOME_UNKNOWN`; do not replay the
upload blindly. The same result applies when a source stream fails or exceeds its limit after an
earlier chunk was consumed by the HTTP transport.

## Paths and data safety

The public path is relative to `data/`. The client rejects absolute paths, `data/`-prefixed paths,
backslashes, empty segments, `.` and `..` segments, control characters, and overlong segments or
paths. The server remains the final authorization and storage authority. A resource path is API
data, not a shell command or a local filesystem path.

Use an operator-selected local source or destination. Never derive a local filename from a server
resource key without an independent path policy. Do not execute a downloaded file. The transfer
methods do not extract archives.

## Authentication and permissions

Resource commands accept either `DICEHUB_API_KEY` or `DICEHUB_SESSION_COOKIE`. Set exactly one.
The CLI keeps both credentials out of command arguments. API-key commands connect to
`https://dicehub.com` by default. Session-based development commands retain their loopback
default. Set `DICEHUB_URL` for another deployment.

The current managed API-key catalog does not expose grants for generic resource metadata or
storage transfers. A managed key therefore cannot be given the narrow access needed by these
commands today. Use a session cookie for current generic storage work. The backend permission
change requires a server update before generic storage can use narrow managed API-key grants.

For app data on the current server, metadata reads and downloads use the legacy `VIEW_APP` check;
uploads and exact-ID deletion use `WRITE_APP_STORAGE`; text reads and replacements use
`EDIT_APP`. Other namespace types use their existing legacy mappings. These broad checks are the
reason this feature does not claim managed API-key support yet.

Do not assume that a key which can list projects, apps, configurations, or runs can access generic
storage. Listing metadata does not imply reading content, uploading, replacing, or deleting it.
The server remains the authority for scope and permission checks.

## CLI

The singular `resource` command exposes the same fixed operations:

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_SESSION_COOKIE=FROM_A_SECRET_MANAGER

dicehub resource list "$DICEHUB_NAMESPACE_ID" --path meshes --type file --recursive --output json
dicehub resource get "$DICEHUB_RESOURCE_ID" --output json
dicehub resource upload "$DICEHUB_NAMESPACE_ID" meshes/cube.stl ./cube.stl --output json
dicehub resource download \
  "$DICEHUB_NAMESPACE_ID" meshes/cube.stl ./downloaded-cube.stl --output json
dicehub resource delete "$DICEHUB_RESOURCE_ID" --yes --output json
```

`resource list` uses `--path`, `--type`, `--recursive`, `--offset`, `--limit`, and `--cursor`.
`resource upload` and `resource download` accept an optional `--max-bytes`. Download refuses an
existing destination unless `--overwrite` is supplied. `resource delete` requires the exact
immutable resource ID and `--yes` before it constructs a client.

JSON output uses the `dicehub.cli/v1` envelope. List and get data contain clean JSON model values.
Upload and download data contain the corresponding receipt model under `upload` or `download`.
Text output is tab-separated and terminal-safe. Successful mutations are sent once. On
`MUTATION_OUTCOME_UNKNOWN`, reconcile the exact namespace, path, or resource ID before retrying.
