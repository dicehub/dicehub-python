---
title: Architecture
description: Package boundaries and rules for extending dicehub-python.
read_when:
  - Adding a new API domain
  - Changing GraphQL transport, models, or CLI structure
---

# Architecture

The repository intentionally uses a top-level `dicehub/` package rather than a `src/` directory.
The distribution name is `dicehub-python`. Python imports and the CLI remain `dicehub`;
distribution metadata lookups and PyInstaller metadata collection use `dicehub-python`.

```text
CLI -> Client      -> sync domain service  -> GraphQLTransport      -> httpx.Client
       AsyncClient -> async domain service -> AsyncGraphQLTransport -> httpx.AsyncClient
```

Each domain, including groups, projects, apps, configurations, resources, storage, runs, teams,
templates, and users, is a vertical package:

```text
dicehub/projects/
├── __init__.py     # stable public exports
├── models.py       # public immutable models
├── service.py      # Python operations and input validation
├── async_service.py # asyncio operations with the same public contract
├── _graphql.py     # fixed documents and private wire models
└── _validation.py  # domain validation when large enough to justify it
```

`client.py` and `async_client.py` each construct one matching transport and explicitly attach
services. `_core/graphql.py` and `_core/async_graphql.py` own HTTP lifecycle and fixed request
execution. They share origin, credential, response, and REST validation rules. `_core/status.py`
maps the common operation status. Domain code never constructs HTTP clients.

Internal imports target leaf modules to prevent facade cycles. Static service registration and
Python GraphQL constants keep wheel and PyInstaller behavior discoverable.

To add a domain:

1. define its public models;
2. add one fixed operation and strict wire response;
3. implement a typed service method;
4. add matching sync and async methods and attach the services explicitly to both clients;
5. export the intended public surface;
6. add contract tests, docs, and an example when useful; and
7. add integration coverage for security-sensitive server authorization.
