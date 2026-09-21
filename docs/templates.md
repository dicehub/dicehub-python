---
title: Templates
description: Discover dicehub app and model templates through the typed SDK and CLI.
read_when:
  - Resolving a template before app creation
  - Filtering templates by name, type, or tags
  - Adding template discovery operations
---

# Templates

`client.templates` provides three fixed read-only GraphQL operations:

- `list()` returns a bounded page from the server template catalog;
- `get(template_id=...)` resolves one immutable template ID; and
- `get_by_route(route=...)` resolves one exact template route.

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    template = client.templates.get_by_route(
        route="/templates/openfoam_snappyhexmesh"
    )
    print(template.template_id, template.name, template.tags)
```

The matching CLI commands are:

```bash
dicehub template list --type APP_TEMPLATE --tag openfoam --output json
dicehub template get "$DICEHUB_TEMPLATE_ID" --output json
dicehub template get-by-route /templates/openfoam_snappyhexmesh --output json
```

Missing or inaccessible templates are rejected through the server's permission status. A
successful response without a template is treated as an incompatible protocol response rather
than silently returning `None`. Resolve the template first and then pass its immutable
`template_id` to `client.apps.create()`; app creation remains an explicit one-shot mutation and is
never hidden inside discovery.

## Pagination and filters

`list()` defaults to app templates, sorted by name, with 20 records per page. It accepts
`search_filter`, `template_type`, `tags`, `order_by`, `order`, `offset`, `limit`, and `cursor`.
Limits are validated before HTTP and capped at 50. Repeated tags form an exact, case-sensitive AND
filter on the server. Pass `template_type=None` only when both app and model templates are
intentionally required. A cursor is meaningful only with the same filters and sort settings that
created it; the returned count is bounded discovery progress, not a guaranteed catalog total.

The supported sort fields are name, created time, and updated time. The server's current
ID-ordering declaration does not match its database key, so the SDK deliberately does not expose
that broken option.

## Security boundary

Discovery returns metadata only: IDs, names, routes, client type, descriptions, image/icon paths,
tags, and timestamps. The server owns catalog inclusion; exact ID and route resolution still apply
its namespace permission check. Discovery does not download template files, initialize user data,
create apps, execute template code, or expose arbitrary GraphQL.

Treat every returned string as untrusted API data. The SDK stores it in immutable strict Pydantic
models. The CLI JSON-encodes values and escapes control characters in text output; it never uses
template routes, names, or paths as local filesystem or shell input.
