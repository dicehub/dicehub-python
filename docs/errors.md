---
title: Errors
description: Stable exception types, codes, exit codes, and retry guidance.
read_when:
  - Handling SDK exceptions
  - Mapping SDK failures into an automation protocol
---

# Errors

All public exceptions inherit from `DiceHubError` and expose a stable `code`, `exit_code`,
`retryable`, and sanitized `as_dict()` payload.

| Type | Code | Meaning |
| --- | --- | --- |
| `ConfigurationError` | `CONFIGURATION_ERROR` | Invalid local configuration or input |
| `AuthenticationRequiredError` | `AUTH_REQUIRED` | Credential missing |
| `AuthenticationError` | `AUTH_FAILED` | Credential rejected or wrong identity mode |
| `TransportError` | `TRANSPORT_ERROR` | Timeout or connection failure |
| `HTTPError` | `HTTP_ERROR` | Non-success HTTP status |
| `GraphQLError` | `GRAPHQL_ERROR` | GraphQL envelope reported errors |
| `APIError` | `API_ERROR` | dicehub operation status failed |
| `ProtocolError` | `PROTOCOL_ERROR` | Incompatible or unsafe response |
| `SelectorResolutionError` | `SELECTOR_RESOLUTION_ERROR` | Exact selector found zero or multiple authorized records |
| `MutationOutcomeUnknownError` | `MUTATION_OUTCOME_UNKNOWN` | Mutation may have completed without a trustworthy response |
| `RunFailedError` | `RUN_FAILED` | Run reached `FAILED`, `INTERRUPTED`, or `CANCELED` |
| `RunTimeoutError` | `RUN_TIMEOUT` | Run did not become terminal before its deadline |

Public exceptions deliberately omit response bodies, GraphQL messages, request headers, and
validation inputs. Use `retryable`; do not infer retries from message text. Mutations require
explicit idempotency before retrying.

For REST file-transfer errors, `APIError.server_code` contains only the recognized `AUTH_ERROR`
or `PERMISSIONS_ERROR` code. Unknown server values are omitted from both the exception field and
its JSON output because those values can contain private response text.

`SelectorResolutionError.selector` identifies the selector kind and `reason` is `NOT_FOUND` or
`AMBIGUOUS`. The error does not echo the untrusted selector value. Resolve the ambiguity or correct
the selector before another call; do not select the first search result.

`MutationOutcomeUnknownError` instances raised by mutation services have `retryable=false`. The
error covers transport, HTTP, GraphQL, or protocol failures where the client cannot prove whether a
non-idempotent mutation ran. Reconcile server state with a read operation before deciding what to
do next; never replay the mutation automatically.

Async task cancellation is not converted to a `DiceHubError`. `AsyncClient` propagates
`asyncio.CancelledError`. A canceled mutation can still have an unknown remote outcome; reconcile
it in the same way as `MutationOutcomeUnknownError` and do not replay it automatically.

`RunFailedError.status` contains the validated terminal `RunStatus`. `RunTimeoutError.last_status`
contains the last validated snapshot, when one was received. Its `retryable=true` value means a
caller may start a new read-only wait after reviewing its own deadline policy. It does not authorize
automatic replay of a run mutation.

The CLI exit codes are 0 for success, 1 for protocol or unexpected internal failure, 2 for local
configuration, 3 for authentication, 4 for API, GraphQL, selector, or terminal run failure, 5 for
transport, HTTP, or uncertain mutation outcome, and 6 for a run wait timeout.
`ProtocolError` retains exit code 1 for compatibility. Use the JSON error code to distinguish it
from an unexpected internal failure.
