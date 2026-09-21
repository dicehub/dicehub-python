---
title: Authentication
description: API-key and development-session authentication rules for the dicehub client.
read_when:
  - Creating a Client
  - Handling API keys or session cookies
  - Building an agent adapter
---

# Authentication

API-key clients and CLI commands connect to the canonical hosted origin, `https://dicehub.com`,
by default. Set `DICEHUB_URL` for CLI commands or pass `base_url` to a client when you use
another deployment. Session-only development commands retain their loopback default. There is
no automatic staging or cross-origin fallback.

Pass exactly one credential to `dicehub.Client`:

- `api_key` is the automation contract and is sent only as one Bearer header.
- `session_cookie` is the explicit browser-session credential for SDK operations that support a
  signed-in user.

Normal CLI resource commands require `DICEHUB_API_KEY`. Only `dicehub api-key`,
`dicehub auth whoami`, top-level group creation, group move, and project move use
`DICEHUB_SESSION_COOKIE`.

The client rejects missing or ambiguous credentials, unsafe origins, invalid credential bytes, and
redirects. It ignores proxy-related environment variables and does not expose response bodies or
credential values through public errors.

`base_url` is trusted operator configuration. API content and CLI arguments cannot override it.
Agent runners should enforce their own approved-origin allowlist before constructing the client.

For hosted onboarding, create and confirm an account at [dicehub signup](https://dicehub.com/signup),
then create a scoped key in [API-key settings](https://dicehub.com/settings/tokens/create). The web
form requires at least one permission. Start with only `VIEW_PROJECT_INFO`; the first
`client.auth.context()` request verifies the key without consuming a resource permission.

Never place credentials in command arguments, source code, project files, examples, or logs. Use
environment injection or a secret manager and rotate temporary credentials after testing.
