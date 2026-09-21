---
title: Runs
description: Machine type discovery, run metadata, bounded waiting, result download, start, and stop operations.
read_when:
  - Listing or inspecting runs through the SDK or CLI
  - Granting managed API keys run permissions
  - Starting or stopping runs through automation
  - Downloading a run result archive
  - Polling run state safely
  - Selecting a machine type and checking its net hourly price
---

# Runs

`client.runs` exposes metadata reads, bounded wait and watch helpers, a bounded result download,
and two independently granted mutations:

```python
import os

import dicehub as dh

with dh.Client(
    base_url=os.environ["DICEHUB_URL"],
    api_key=os.environ["DICEHUB_API_KEY"],
) as client:
    page = client.runs.list(
        namespace_id=os.environ["DICEHUB_PROJECT_ID"],
        include_descendants=True,
        states=[dh.RunState.RUNNING, dh.RunState.PENDING],
    )
    run = client.runs.get(run_id=os.environ["DICEHUB_RUN_ID"])
    status = client.runs.status(run_id=run.run_id)
```

Managed API keys require `VIEW_RUN_INFO` for list, get, and status metadata inside the key's fixed
personal, group, or project scope. `DOWNLOAD_RUN_RESULT`, `START_RUN`, and `STOP_RUN` are separate
grants; none implies metadata access or another operation. Legacy `VIEW_RUN` and `EDIT_RUN` remain
broader, noncatalog permissions for compatibility; new managed keys do not receive them.

`VIEW_RUN_INFO` does not grant access to:

- environment variables, user data, input/output data, creators, or cost information;
- logs, result archives, reports, generic storage, or S3 credentials;
- run creation, start, stop, cancel, archive, update, or deletion; or
- app or configuration metadata.

`DOWNLOAD_RUN_RESULT` grants only the result archive for an authorized run. `START_RUN` and
`STOP_RUN` do not expose any read capability. A key that also needs to inspect lifecycle state must
receive `VIEW_RUN_INFO` explicitly.

## Machine types and prices

`list_machine_types()` returns the current machine catalog in server order. Each immutable record
contains only its machine type ID, CPU count, GPU count, RAM in GB, a deterministic description,
and its price. The nested price is the net EUR price for one machine-hour; its decimal amount is
never calculated with a binary float. Local machines have `price=None` and may have unknown
hardware counts.

```python
for machine in client.runs.list_machine_types():
    if machine.price is not None:
        print(machine.machine_type_id, machine.price.amount, machine.price.currency)
```

The SDK joins the fixed machine and product operations internally. Product IDs, providers, usage
multipliers, storage, scheduling flags, and tax data are not part of the public model. It fails
closed if the server returns duplicate, missing, malformed, non-net, or inconsistent price data.
The executable [machine discovery example](../examples/list_machine_types.py) prints one JSON record
per machine.

## List

`list()` requires an exact namespace ID. It searches that namespace only unless
`include_descendants=True` is explicit. Project-scoped automation normally passes its project ID
and enables descendants because runs belong to apps below the project.

Results are bounded to 50 per page. Filters accept exact app IDs, run types, and run states.
Duplicate or empty enum filters are rejected locally. The default order is newest creation first.

## Get and status

`get()` returns safe operational and scheduling metadata. It deliberately omits all content and
identity-bearing fields listed above.

`status()` uses a separate minimal GraphQL selection for frequent state checks. It returns one
snapshot and never waits or polls implicitly. `state` is the current lifecycle state;
`execution_status` is a separate server value and may be absent or differ while post-processing is
active. Timestamps are timezone-aware UTC datetimes.

Run names, machine identifiers, module names, flows, queues, study IDs, and batch values remain
untrusted server data. Do not execute them or interpolate them into shell commands or filesystem
paths.

## Wait and watch

`wait()` polls the same fixed status operation to a monotonic deadline. It returns the terminal
snapshot for `FINISHED` or `STOPPED`. It raises `RunFailedError` for `FAILED`, `INTERRUPTED`, or
`CANCELED`, and raises retryable `RunTimeoutError` if the deadline expires first.

```python
try:
    terminal = client.runs.wait(
        run_id=os.environ["DICEHUB_RUN_ID"],
        timeout_seconds=3600,
        poll_seconds=2,
    )
except dh.RunFailedError as error:
    print(error.status.state.value)
    raise
```

`watch()` is a synchronous iterator. It yields the first snapshot, then only lifecycle-relevant
changes to `state`, `execution_status`, `error`, or `flags`. A timestamp-only refresh is not an
event. The terminal snapshot is yielded once, including a failed terminal state, and iteration then
stops. Close the iterator to cancel it; the SDK creates no thread or background task.

```python
for status in client.runs.watch(
    run_id=os.environ["DICEHUB_RUN_ID"],
    timeout_seconds=3600,
):
    print(status.state.value)
```

With `AsyncClient`, `wait()` is awaited and `watch()` is consumed with `async for`. The deadline,
change filtering, terminal states, and errors are identical. Close a stored async iterator with
`await statuses.aclose()`.

Both methods require an explicit timeout no greater than 7 days. The polling interval must be
finite, at least 0.1 seconds, and no greater than the timeout. Each HTTP connect, pool, write, and
read timeout is capped by the smaller of the client's timeout and the remaining deadline. HTTPX
applies these limits per network phase, so timeout delivery can occur after the nominal deadline;
the SDK checks the monotonic deadline again before it yields or returns a response. The helpers
never retry start, stop, or any other mutation. A transport failure before the overall deadline
remains a `TransportError`; callers decide whether a new read-only wait is suitable.

The executable [wait example](../examples/wait_for_run.py) obtains the origin, key, and exact run ID
from the environment.

## Download results

`download_results()` performs one GET against the fixed result-archive route for an exact run UUID.
It streams into a caller-owned binary destination, returns the byte count, and rejects responses
larger than 2 GiB. That ceiling is a deliberate SDK hard limit: `max_bytes` can reduce it but cannot
increase it.

```python
from pathlib import Path

destination = Path("run-results.zip")
with destination.open("xb") as stream:
    count = client.runs.download_results(
        run_id=os.environ["DICEHUB_RUN_ID"],
        destination=stream,
    )
print(count)
```

This ZIP is the server's downloadable result snapshot, not a complete run archive. It omits entries
under `VTK/`, and a request before the run reaches `FINISHED` may return an empty or incomplete ZIP.
Check `status()` or `wait()` separately and decide whether the resulting lifecycle state is
acceptable before downloading. Result download does not infer completeness.

The SDK never derives a local filename from response headers or run metadata. A failed streaming
request may have written a prefix to the caller's destination; callers own cleanup. The CLI handles
this with an exclusive new file or a same-directory temporary file plus atomic replacement. The
executable [download example](../examples/download_run_results.py) removes a newly created partial
file on failure.

## Results-panel S3 credentials

`get_result_s3_credentials()` wraps the same result-folder lookup and credential mutation used by
the dicehub Results panel. It does not create a separate credential type.

```python
credentials = client.runs.get_result_s3_credentials(
    app_id=os.environ["DICEHUB_APP_ID"],
    run_id=os.environ["DICEHUB_RUN_ID"],
)
```

The access key and secret are `SecretStr` values. Keep them in memory and reveal them only when
configuring an S3 client. The dicehub S3 endpoint is `<DICEHUB_URL>/api/v1/s3` and is read-only.
This legacy Results-panel flow requires broad `VIEW_APP` access. It is separate from the narrow
`DOWNLOAD_RUN_RESULT` archive permission.

With the default `regenerate=False`, dicehub returns the current pair and creates one only if the
folder has no pair. `regenerate=True` rotates the pair and invalidates the previous credentials.
Credential issuance is sent once and is never retried automatically. After
`MUTATION_OUTCOME_UNKNOWN`, do not repeat a rotation until you reconcile the active pair.

## Start

`start()` starts the exact configuration using the exact machine type. Node count defaults to one;
CPU count is optional because fixed machine types may decide it server-side. Counts must be positive
GraphQL integers, `notify` must be a real boolean, and machine type IDs use the server's ASCII enum
identifier format.

```python
started = client.runs.start(
    config_id=os.environ["DICEHUB_CONFIG_ID"],
    machine_type_id=os.environ["DICEHUB_MACHINE_TYPE_ID"],
    node_count=1,
    notify=False,
)
print(started.run_id, started.state.value)
```

The returned `RunStatus` is the server's immediate snapshot, not proof that execution reached
`RUNNING`. Starting may consume quota or incur charges. If the configuration references a prior
terminal run, dicehub archives it as part of the transactional replacement. The CLI therefore
requires `--yes`; the Python method is direct so callers can build their own approval policy. A
network failure can still leave the client unable to determine the mutation's committed outcome.

Managed API-key identities have no human notification recipient and must leave `notify=False`.
`notify=True` remains available to authenticated sessions and compatible legacy callers; the server
rejects it with `BAD_PARAMETERS` for a managed key.

The executable [start example](../examples/start_run.py) additionally requires
`DICEHUB_CONFIRM_START_CONFIG_ID` to exactly match `DICEHUB_CONFIG_ID`.

## Stop

`stop(run_id=...)` submits one stop request for an exact immutable run UUID and returns `None` when
dicehub accepts it. Stopping is asynchronous: acceptance does not mean the run is already terminal.
Read `status()` or use a bounded `wait()` when the caller needs a later terminal snapshot. The CLI
requires `--yes` and says "Stop requested" for the same reason.
The executable [stop example](../examples/stop_run.py) additionally requires
`DICEHUB_CONFIRM_STOP_RUN_ID` to exactly match `DICEHUB_RUN_ID`.

Start and stop are non-idempotent network operations from the client's perspective. They are sent
once and never retried. `MUTATION_OUTCOME_UNKNOWN` means dicehub may have applied the mutation; use
an independently authorized status read to reconcile the exact run or configuration before taking
another action.

## CLI

The combined example below assumes the configured key has each permission needed by the commands
it runs: `VIEW_RUN_INFO`, `DOWNLOAD_RUN_RESULT`, `START_RUN`, and `STOP_RUN`. Separate keys remain
preferable when one automation process does not need all four capabilities.

```bash
export DICEHUB_URL=https://dicehub.com
export DICEHUB_API_KEY=FROM_A_SECRET_MANAGER

dicehub run list "$DICEHUB_PROJECT_ID" --include-descendants --output json
dicehub run get "$DICEHUB_RUN_ID" --output json
dicehub run status "$DICEHUB_RUN_ID" --output json
dicehub run wait "$DICEHUB_RUN_ID" --timeout 3600 --output json
dicehub run watch "$DICEHUB_RUN_ID" --timeout 3600 --output jsonl
dicehub run download-results "$DICEHUB_RUN_ID" ./run-results.zip --output json
dicehub run start "$DICEHUB_CONFIG_ID" \
  --machine-type "$DICEHUB_MACHINE_TYPE_ID" \
  --nodes 1 \
  --yes \
  --output json
dicehub run stop "$DICEHUB_RUN_ID" --yes --output json
```

`run status` returns one snapshot under `data.run_status`. `run wait` returns one successful
terminal snapshot or one structured error. `run watch --output jsonl` writes one compact
`dicehub.cli/v1` envelope per status change. A failed terminal state is followed by one error
envelope and exit code 4; timeout uses exit code 6. Repeated `--type` and `--state` options construct
explicit filters. Credentials and the destination origin remain environment-only. Result download
requires an explicit destination and refuses to overwrite unless `--overwrite` is supplied. `run
start` returns its immediate snapshot under `data.run_status`.

Run log streaming is not exposed. The current server operation does not provide a narrow managed
API-key permission, bounded content chunks, or an explicit stable end-of-stream contract.
