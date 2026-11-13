---
title: REST v2 transport
description: Use REST v2 for existing synchronous and asynchronous SDK services.
read_when:
  - Enabling REST v2 in the Python SDK
  - Comparing REST v2 workflows with GraphQL
---

# REST v2 transport

Set `api_protocol="rest_v2"` on `Client` or `AsyncClient` to use REST v2 for
all existing SDK JSON operations. GraphQL remains the default. The server must
have `REST_API_V2_ENABLED=true` and this version of the REST routes enabled.
Requests fail if the server lacks a required route; there is no GraphQL fallback.

```python
import os
from dicehub import Client

with Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
    api_protocol="rest_v2",
) as client:
    for project in client.projects.list(limit=20).projects:
        print(project.project_id, project.name)
```

The option covers the existing methods in `auth`, `api_keys`, `apps`, `configs`,
`groups`, `projects`, `resources`, `runs`, `teams`, `templates`, and `users`,
including membership operations. It preserves public models and method signatures.
The CLI keeps its default GraphQL transport. Server operations that have no public
SDK method, such as billing or signup administration, remain available through
REST directly and its OpenAPI document.

Configuration uploads, downloads, storage transfers, and result archives continue
to use their existing binary REST v1 endpoints. The JSON configuration/file/run
workflow can therefore use REST throughout. Starting runs requires the same grants
and can incur charges. SDK transport selection does not enable compute or payment
providers on the server.

`project_reads="rest_v2"` remains supported for a gradual migration of only project
list, ID, and route reads. `api_protocol="rest_v2"` selects REST for all supported
operations, including those project reads. Both options use one HTTP client.

## Open compatibility issue

The current REST server defaults an omitted `is_published` app filter to `false`.
The SDK's `apps.list(is_published=None)` therefore excludes published apps in REST
mode, while GraphQL includes both published and unpublished apps. Use GraphQL when
you need the combined list. Explicit `True` and `False` filters work in both modes.
The server must support the unfiltered case before this transport can preserve
the default app-list behavior.

## Pagination and representations

Page size remains 1–50. REST offsets are limited to `2**31 - 1` and decimal IDs to
`2**63 - 1`; invalid values fail before HTTP. UUIDs use canonical path encoding.
Project, app, and group lists and team reads by route request `view=summary`.
These queries omit large descriptions and other unused detail fields.
Detail wire fields such as timestamps and owner type are validated without changing
the public project model.

Pass the returned `cursor` and the next `offset` with the same filters and sort.
`count` is the server's known row count; it can grow as pages are read and is not
an exact total. Start without a cursor after changing filters or sort. Concurrent
changes can affect page contents. Cursors never grant access to a resource.
Membership pages preserve inherited rows; `deduplicate=True` selects the nearest
visible membership before sorting and pagination.

## Errors and request safety

Both clients preserve fixed-origin requests, TLS verification, credential selection,
timeouts, response limits, and close handling. Redirects are not followed. Credentials
stay in Bearer headers or session cookies. JSON writes include the required
`X-Dicehub-Request: rest-v2` header and run once without retries.

HTTP 401 raises `AuthenticationError`. HTTP 403, 404, and 422 raise a generic
`APIError` with a fixed permission, not-found, or validation code. A 404 can also mean
the server lacks the route. Read transport failures raise `TransportError` or
`HTTPError`; invalid response data raises `ProtocolError`. Unconfirmed writes raise
`MutationOutcomeUnknownError`. Check server state before retrying. Error objects
retain no server body, credential, or original exception chain. Creation secrets
use `SecretStr` and require explicit extraction by the caller.

Response cursors are limited to 16,384 characters. Resource text reads retain the
2 MiB UTF-8 byte limit, including multibyte content. Invalid cursor or credential
fields raise sanitized SDK errors. A failed result-folder lookup remains a read
error; only an unconfirmed credential write reports an unknown mutation outcome.

## Live comparison

Use a disposable deployment and credentials from the environment:

```sh
export DICEHUB_LIVE_TEST=1
export DICEHUB_LIVE_REST_V2_TEST=1
export DICEHUB_URL=http://127.0.0.1:18090
export DICEHUB_LIVE_PROJECT_ID=42
pytest tests/integration/test_live_rest_v2_projects.py
```

Set exactly one of `DICEHUB_API_KEY` or `DICEHUB_SESSION_COOKIE` through your secret
manager. The test compares both clients' detail, route, filter, sort, and multi-page
results with GraphQL. It performs reads only. Use a deployment with more than one visible
project to exercise page continuation. Set `DICEHUB_LIVE_USER_ID` to also compare
user-membership filtering. Rotate temporary test credentials after the run.
