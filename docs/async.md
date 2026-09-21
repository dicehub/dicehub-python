---
title: Asynchronous SDK
description: Use AsyncClient for concurrent asyncio-based dicehub automation.
read_when:
  - Calling dicehub from an asyncio application
  - Migrating code from Client to AsyncClient
  - Handling cancellation during dicehub requests
---

# Asynchronous SDK

`AsyncClient` provides the same typed services, method names, parameters, validation, models, and
permission boundaries as `Client`. Network requests use `httpx.AsyncClient`; they do not run the
synchronous client in a worker thread.

```python
import asyncio
import os

import dicehub as dh


async def main() -> None:
    async with dh.AsyncClient(
        base_url=os.environ["DICEHUB_URL"],
        api_key=os.environ["DICEHUB_API_KEY"],
    ) as client:
        context = await client.auth.context()
        projects = await client.projects.list(limit=20)
        print(context.identity_mode.value, len(projects.projects))


asyncio.run(main())
```

Use `await client.aclose()` when an async context manager is not suitable. Closing is idempotent;
requests after close raise `ConfigurationError`.

## Service parity

All service attributes are available on both clients: `auth`, `api_keys`, `apps`, `configs`,
`groups`, `projects`, `resources`, `runs`, `storage`, `teams`, `templates`, and `users`. Add `await`
to each ordinary SDK call. Page models and explicit cursor behavior do not change.

`runs.watch()` returns an async iterator:

```python
async for status in client.runs.watch(
    run_id=os.environ["DICEHUB_RUN_ID"],
    timeout_seconds=3600,
):
    print(status.state.value)
```

Call `await statuses.aclose()` to stop a stored watch iterator before its next poll.

## Files and cancellation

Binary methods keep the existing `BinaryIO` and local-path interfaces. HTTP transfer is native
async. Reads, writes, and filesystem operations for caller-provided local objects run in worker
threads so they do not block the event loop. The SDK does not close caller-owned streams.

Task cancellation propagates as `asyncio.CancelledError`. A canceled mutation may already have
reached dicehub, so its remote outcome can be unknown. Reconcile state with a read operation before
you decide whether another mutation is safe. The SDK never retries mutations automatically.

The async API supports asyncio only. It adds no async CLI commands and no new dependency.
