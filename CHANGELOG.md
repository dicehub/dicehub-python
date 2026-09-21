# Changelog

## dicehub-python 0.10.0 public distribution - 2026-09-20

- Redact unknown REST error codes from SDK exceptions and CLI JSON for sync and async file transfers.
- Rename the distribution to `dicehub-python` for public PyPI installation. Preserve the `dicehub`
  Python import and CLI command; prepare manual publication and download verification in GitLab CI.
- License the SDK under MIT, copyright 2026 dicehub GmbH, and include the license in release archives.
- Prepare public source distribution, contributor and security documentation, and GitLab checks
  for a public GitHub mirror. GitLab remains the source repository and only CI system.
- Restrict package source archives to SDK, documentation, examples, requirements, tests, and build
  support files. Check archive contents, documentation links, and standalone CLI commands in CI.
- Make the existing `ProtocolError` exit code 1 explicit and document the complete CLI exit mapping.

## 0.10.0 - 2026-08-30

- Add typed sync and async machine type discovery with current net EUR machine-hour prices,
  deterministic hardware descriptions, local-machine handling, and matching CLI output.

## 0.9.0 - 2026-08-30

- Add typed app role and direct membership management, independent app-member grants, exact
  selector-based creation, sync and async parity, and deterministic CLI commands. Inherited
  memberships remain read-only and mutations remain ID-only.

## 0.8.0 - 2026-08-29

- Add the `client.teams` lookup service, project role and membership management, exact
  permission-scoped username, namespace-route, team-route, and role-name discovery for group and
  project member creation, matching sync and async services, and deterministic CLI selector
  output. Final mutations remain ID-only.
- Add `AsyncClient` with asyncio-native HTTP transport and full typed service parity, async run
  watching, bounded binary transfers, cancellation propagation, and no automatic mutation retries.

## 0.7.0 - 2026-08-28

- Add typed generic data-resource metadata and text operations, exact-ID deletion, bounded binary
  storage transfers, local SHA-256 receipts, atomic file downloads, and matching deterministic
  resource CLI commands. Current generic server permissions remain legacy and broad; narrow
  managed API-key grants and server-confirmed integrity are tracked in `dicehub#3353`.
- Define the public hosted onboarding contract for `https://dicehub.com`, including account and
  API-key setup, least-privilege first workflows, deterministic authentication checks, credential
  lifecycle guidance, and placeholder-origin regression coverage.

## 0.6.0 - 2026-08-27

- Add bounded `client.runs.wait()` and change-only `client.runs.watch()` status polling, typed
  terminal-failure and timeout errors, and deterministic `dicehub run wait/watch` output.
- Defer run log streaming until dicehub provides a permission-scoped, cursor-based content API.

## 0.5.0 - 2026-08-27

- Require dicehub server `0.22.1` or newer for group automation and `0.22.6` or newer for
  `client.configs.set_values()`.
- Add `client.configs.set_values()` and the immutable `ConfigValueUpdate` model for bounded, scalar
  batch updates in existing YAML configuration resources; ambiguous mutation outcomes are never
  retried.
- Add typed permission-scoped group list, exact-ID, and exact-route discovery through
  `client.groups` and the deterministic `dicehub group` CLI.
- Add one-shot `client.groups.update()` and `dicehub group update`; managed API keys need
  `EDIT_GROUP_INFO` inside their fixed scope, and ambiguous outcomes are never retried.
- Add typed subgroup creation, recursive group deletion, avatar changes, role discovery, and
  user/team membership management through `client.groups` and matching `dicehub group` commands.
  Managed API keys stay inside their fixed group scope; top-level creation and moves remain
  session-only.

## 0.4.0 - 2026-08-16

- Add create-time managed API-key activation and expiration timestamps, validity metadata and
  status, and matching `dicehub api-key create --not-before/--expires-at` controls.
- **Breaking:** Require `DICEHUB_API_KEY` and `DICEHUB_URL` for normal CLI automation commands;
  remove the implicit browser-session fallback while keeping explicitly session-only commands
  separate.
- Prompt for confirmation when `dicehub project delete` runs in an interactive terminal, while
  retaining `--yes` as the required non-interactive automation control.
- Add fixed `client.configs.import_geometry()` STL conversion with typed conversion and optional
  first-import setup run snapshots, an ordered server-owned queue, and one-request mutation-outcome
  semantics.
- Extend the controlled-cube workflow with server-generated geometry, background mesh, material
  point, and camera validation; narrow refinement and camera-roll edits; three-run cleanup; and
  validated result download.
- Add an incremental car-mesh example with a bundled STL and direct dicehub-python calls.
- Expose the existing Results-panel S3 credentials through `client.runs` for optional read-only
  result downloads.

## 0.3.0 - 2026-08-13

- Add typed `client.templates.list()`, `.get()`, and `.get_by_route()` discovery plus deterministic
  `dicehub template` CLI commands, and make the controlled-cube workflow resolve its stable
  template route without an operator-supplied numeric ID.
- Add typed `client.api_keys.create()`, `.list()`, and `.delete()` operations over the public
  GraphQL API.
- Protect one-time API-key values with `SecretStr` and keep list responses metadata-only.
- Add mocked API contract coverage and a double-opt-in local create/use/delete/revocation test.
- Complete session-only managed-key administration in the SDK and `dicehub api-key` CLI, with
  protected one-time secret delivery through a required non-stdio `--secret-fd` pipe or socket.
- Make managed API-key listing transparently aggregate fixed 20-record cursor pages while preserving
  its tuple and CLI contracts, per-response limits, strict ordering, and bounded progress guards.
- Reorganize the SDK into explicit core, domain, and CLI packages under top-level `dicehub/`.
- Add typed, permission-scoped `client.projects.list()` project discovery.
- Add typed, permission-scoped `client.apps.list()`, `.get()`, and `.get_by_route()` app metadata
  discovery plus `client.apps.create()` and deterministic `dicehub app` CLI commands.
- Allow managed API keys with `CREATE_APP` to create apps inside projects covered by their fixed
  personal, group, or project scope; require exact project and template IDs and surface ambiguous
  mutation outcomes as non-retryable errors.
- Add typed `client.apps.update()` and `dicehub app update`; managed API keys need the narrow
  `EDIT_APP_INFO` grant inside their fixed scope, without receiving broader app-write capabilities.
- Add typed `client.apps.delete()` and guarded `dicehub app delete APP_ID --yes`; managed API keys
  need `DELETE_APP` inside their fixed scope, and ambiguous deletion outcomes are never retried.
- Add typed `client.configs.list()` and `.get()` plus deterministic `dicehub config list/get`
  commands for metadata-only discovery with the narrow `VIEW_CONFIG_INFO` grant.
- Add typed `client.configs.create()` and deterministic `dicehub config create`; managed API keys
  need `CREATE_CONFIG` inside their fixed scope, explicit clone sources must belong to the same app,
  and ambiguous creation outcomes are never retried.
- Add complete permission-scoped configuration editing: metadata updates, text listing/reads/writes,
  streamed binary upload/download, and permanent content deletion through the SDK and CLI.
- Add typed `client.configs.delete()` and guarded `dicehub config delete CONFIG_ID --yes`; managed
  API keys need `DELETE_CONFIG` inside their fixed scope, and deletion is never retried.
- Add typed `client.runs.list()`, `.get()`, and `.status()` plus deterministic `dicehub run`
  commands. Managed keys need `VIEW_RUN_INFO`; responses deliberately exclude content, identity,
  cost, artifact, storage, and mutation capabilities.
- Add one-shot `client.runs.start()` and `.stop()` mutations plus guarded `dicehub run start/stop`
  commands. Managed keys need independent `START_RUN` and `STOP_RUN` grants; ambiguous outcomes
  are never retried.
- Add bounded `client.runs.download_results()` streaming and atomic
  `dicehub run download-results` output with the independent `DOWNLOAD_RUN_RESULT` grant.
- Add a double-opt-in controlled-cube example covering private project and app creation, STL
  config-content upload, local OpenFOAM execution, bounded polling, validated result-ZIP download,
  and exact project cleanup.
- Add typed project get, create, update, move, and delete operations plus a deterministic
  `dicehub project` CLI surface.
- Allow personal-scoped API keys with `CREATE_USER_PROJECT` and group-scoped keys with
  `CREATE_PROJECT` to create projects; allow permission-scoped keys to update projects and delete
  projects within their fixed scope with `DELETE_PROJECT`; keep move session-only and report
  ambiguous mutation outcomes as non-retryable errors.
- Prevent sanitized SDK and CLI failures from retaining secret-bearing exception contexts.
- Add layered tests, Astro-ready Markdown documentation, executable examples, and wheel and
  PyInstaller smoke gates.

## 0.2.0 - 2026-08-04

- **Breaking:** Replace the public `DiceHub` class with `Client`; the compact import style is
  `import dicehub as dh`.
- Add API-key Bearer authentication and typed `client.auth.context()` support.
- Add deterministic `dicehub auth status` JSON output for agent authentication checks.

## 0.1.0 - 2026-08-02

- Initial project setup.
- Add the typed, read-only `users.me` SDK operation.
- Add deterministic `dicehub auth whoami` JSON output.
- Add mocked contract tests and an opt-in local API smoke test.
- Bind CLI session credentials to the environment-configured origin and cap response bodies.
- Add a GitLab CI quality, build, and installed-wheel smoke gate.
- Publish the `dicehub` distribution exclusively to the private GitLab Python Package Registry.
