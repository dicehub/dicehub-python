---
title: Public hosted onboarding contract
description: Decision record for the supported dicehub-python first-use path.
read_when:
  - Changing installation, authentication, or first-use documentation
  - Adding a default origin or credential fallback
---

# Public hosted onboarding contract

Status: Accepted on 2026-08-27; hosted-origin default updated on 2026-09-15.

## Decision

- The canonical hosted origin is exactly `https://dicehub.com`.
- New hosted users self-register at `https://dicehub.com/signup`, confirm their email address, and
  sign in at `https://dicehub.com/signin`. Account invitation is not an SDK onboarding step.
- The first automation credential is a personal-scoped key created at
  `https://dicehub.com/settings/tokens/create`. The user stores its one-time secret outside dicehub.
- The first key has only `VIEW_PROJECT_INFO`. A separate first mutation key has only
  `CREATE_USER_PROJECT`, unless one process must also list projects.
- API-key clients and CLI commands use `https://dicehub.com` by default. Another deployment must
  be selected explicitly. There is no staging or cross-origin fallback.
- Public onboarding documents the hosted service. The SDK can use another operator-approved origin,
  but self-hosted account and deployment provisioning are outside this guide.
- Public source installation does not require registry credentials. Hosted service credentials
  remain separate from package installation.

## Consequences

The first-use sequence is account creation, email confirmation, SDK installation, API-key creation,
environment injection, and `client.auth.context()` or `dicehub auth status --output json`.
Documentation uses environment-provided credentials. Placeholder origins are rejected by the test
suite.

Rotation means create a replacement, update and verify the consumer, and revoke the old key. A lost
key is never recovered. No example puts a credential in a command argument, URL, source file, or
expected error.
