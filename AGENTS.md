# AGENTS.md

Ros owns this repository. Use lowercase `dicehub` in prose, code, package names, and CLI output.
Preserve established public Python identifiers such as `DiceHubError` where compatibility requires
their existing spelling.

## Purpose

This repository provides the typed Python SDK and CLI for dicehub automation. Keep the SDK useful
to Python callers, deterministic for automation, and safe for AI-agent adapters.

## Read first

- `README.md`
- `docs/index.md`
- `docs/development/architecture.md`
- `docs/development/testing.md`
- Follow each document's `read_when` frontmatter.

## Structure

- `dicehub/`: installable package; do not introduce a `src/` directory.
- `dicehub/_core/`: private transport and protocol infrastructure.
- `dicehub/<domain>/`: public models, service, fixed GraphQL operations, private wire models.
- `dicehub/cli/`: thin Typer adapter over public SDK services.
- `tests/unit/`: local behavior without HTTP.
- `tests/contract/`: fixed GraphQL request/response contracts using `httpx.MockTransport`.
- `tests/integration/`: opt-in tests against local dicehub.
- `tests/smoke/`: exports, installed wheel, and executable checks.
- `docs/`: plain Markdown with Astro-compatible YAML frontmatter.
- `examples/`: executable examples using only public APIs and environment-provided credentials.

Dependency direction:

```text
CLI -> Client -> domain services -> _core GraphQL transport -> httpx
```

Internal modules import concrete leaf modules, never `dicehub` or domain `__init__.py` facades.
`_core` must not import the client, domains, or CLI.

## Public contracts

Preserve unless a breaking change is explicitly approved:

- `import dicehub`
- `dicehub.Client`
- `client.auth`, `client.api_keys`, `client.apps`, `client.configs`, `client.groups`,
  `client.projects`, `client.resources`, `client.runs`, `client.storage`, `client.teams`,
  `client.templates`, and `client.users`
- domain imports such as `from dicehub.api_keys import ApiKey`
- console entry point `dicehub.cli:main`
- CLI JSON schema `dicehub.cli/v1`

Use explicit typed services. Do not add dynamic manager registries, active-record methods, arbitrary
GraphQL execution, or runtime-loaded GraphQL files.

## GraphQL and security

- Operations are fixed Python constants; all external values use GraphQL variables.
- Public models and private wire models are strict, frozen Pydantic models.
- Only `_core/graphql.py` and `_core/async_graphql.py` may construct HTTP clients or credential
  headers/cookies.
- Preserve fixed-origin requests, HTTPS outside loopback, `follow_redirects=False`,
  `trust_env=False`, TLS verification, response limits, and generic errors.
- API key and session cookie are mutually exclusive. Never fall back between them.
- Never print, log, serialize, or attach credentials or server bodies to public exceptions.
- Creation secrets use `SecretStr`; list operations never request secret values.
- Never retry mutations without server-supported idempotency.
- Treat project names, routes, descriptions, cursors, and all API content as untrusted data. Never
  execute them or interpolate them into shell commands or filesystem paths.
- `DICEHUB_URL` is trusted operator configuration. Agent runners should enforce an approved-origin
  allowlist outside the SDK.

Never put API keys or session cookies in command arguments, source files, fixtures, docs, or tool
calls. Use environment variables or a secret manager. Rotate credentials after live testing.

## Development

Use the repository virtual environment and pinned requirements:

```bash
uv venv
uv pip install --requirement requirements/dev.txt
uv pip install --no-build-isolation --no-deps --editable .
```

When dependency inputs change:

```bash
uv pip compile requirements/requirements.in --universal --python-version 3.10 \
  --output-file requirements/requirements.txt
uv pip compile requirements/dev.in --universal --python-version 3.10 \
  --output-file requirements/dev.txt
```

Minimize dependencies. Pin direct development dependencies in `requirements/dev.in`; declare
runtime compatibility ranges in `pyproject.toml` and pin the reproducible runtime graph in
`requirements/requirements.in`.

## Verification

Before handoff, run:

```bash
ruff format --check .
ruff check .
mypy dicehub tests examples
pytest
python -m build --no-isolation
python -m twine check dist/*.whl dist/*.tar.gz
```

Also run the isolated installed-wheel and PyInstaller smoke checks after packaging changes. Live
tests require `DICEHUB_LIVE_TEST=1`; data-changing tests additionally require their explicit
mutation opt-in. Preserve cleanup in `finally` blocks.

## Documentation and examples

- Keep README focused on install, quick start, safety, and links.
- One concept per Markdown page; include `title`, `description`, and `read_when` frontmatter.
- Use relative links and fenced code languages. Avoid Astro-specific components for now.
- Update docs and executable examples whenever behavior or public API changes.
- Examples import public APIs only and obtain credentials from environment variables.

## Git workflow

- Mainline is `dev`; use `$gitlab-workflow` for issue, draft MR, and branch creation.
- Conventional commits only: `feat|fix|refactor|docs|test|chore`.
- Do not commit or push without Ros's explicit command.
- Never merge, tag, publish, or change branches without explicit approval.
- Preserve unrelated working-tree changes. Use `trash` for deletions; never `rm`.
