---
title: Getting started
description: Create a hosted dicehub account, install the SDK, and verify an API key.
read_when:
  - Installing dicehub-python
  - Writing a first SDK script
---

# Getting started

This is the supported first-use path for hosted dicehub at `https://dicehub.com`.

## Create an account

1. Open [dicehub signup](https://dicehub.com/signup).
2. Enter your name, email address, username, and password, accept the terms, and select **Sign up**.
3. Open the confirmation email and confirm the address before you create an automation credential.
4. Sign in at [dicehub login](https://dicehub.com/signin) when the browser session has ended.

The current hosted path uses self-signup. There is no separate SDK account-invitation step. A group
administrator can add your registered account to a group after signup.

## Install the SDK

Use CPython 3.10 through 3.14. Install the `dicehub-python` distribution from PyPI:

```bash
pip install dicehub-python
```

The distribution installs the `dicehub` Python package and the `dicehub` command. Use a fresh
environment when moving from the earlier `dicehub` distribution; the two distributions install
the same module and command. Package installation and hosted service authentication are separate;
an API key is used only when calling dicehub.

## Create a personal API key

1. Open [API-key settings](https://dicehub.com/settings/tokens/create).
2. Give the key a clear name such as `first SDK key`.
3. Select only `VIEW_PROJECT_INFO` for the first read-only workflow.
4. Set a short expiration, review the fixed personal scope, and create the key.
5. Store the secret immediately in a secret manager. It is shown only once.

Do not use an administrator grant for the first key. To rotate it, create a replacement, update the
consumer, verify the replacement, and revoke the old key at
[API-key settings](https://dicehub.com/settings/tokens).

## Verify authentication

Set the API key for the current shell:

```bash
read -rsp "dicehub API key: " DICEHUB_API_KEY && export DICEHUB_API_KEY
printf '\n'
dicehub auth status --output json
```

The successful output is deterministic:

```json
{"schema_version":"dicehub.cli/v1","ok":true,"data":{"identity_mode":"API_KEY"},"error":null}
```

The equivalent first Python request is:

```python
import os

import dicehub as dh

with dh.Client(api_key=os.environ["DICEHUB_API_KEY"]) as client:
    print(client.auth.context().identity_mode.value)
```

The executable [`auth_status.py`](../examples/auth_status.py) example uses the same environment-only
contract.

## Add only the next permission

| Workflow | Minimum personal-key permission |
|---|---|
| Verify authentication with `client.auth.context()` | No resource grant is consumed; the web form requires one, so keep only `VIEW_PROJECT_INFO` |
| List visible projects with `client.projects.list()` | `VIEW_PROJECT_INFO` |
| Create a personal project with `client.projects.create()` | `CREATE_USER_PROJECT` |

Use a separate short-lived key for the mutation when the read-only process does not need it. If one
process must create and then list projects, grant only `CREATE_USER_PROJECT` and `VIEW_PROJECT_INFO`.

The SDK and CLI connect to `https://dicehub.com` by default. Set `DICEHUB_URL` or pass
`base_url` for another deployment. Plain HTTP is accepted only for loopback development.
Self-hosted provisioning is outside this hosted onboarding guide.

Continue with [authentication](authentication.md), [managed API keys](api-keys.md),
[projects](projects.md), or the executable scripts in `examples/`. Use
[dicehub support](https://dicehub.com/contact-us) for account or credential-UI
problems.
