---
title: Testing
description: Local quality gates, test layers, wheel smoke, and frozen executable checks.
read_when:
  - Running or adding tests
  - Changing packaging or executable behavior
---

# Testing

The installed distribution is `dicehub-python`; imports and the executable remain `dicehub`.
Create a fresh virtual environment when migrating from the former `dicehub` distribution so that
old metadata and console scripts cannot mask a packaging failure.

Install the pinned development environment, then run the full local gate:

```bash
uv pip install --requirement requirements/dev.txt
uv pip install --no-build-isolation --no-deps --editable .
ruff format --check .
ruff check .
mypy dicehub tests examples scripts
python scripts/check_docs.py
pytest
python -m build --no-isolation
python -m readme_renderer README.md -o /tmp/dicehub-python-readme.html
python -m twine check dist/*.whl dist/*.tar.gz
python scripts/check_dist.py
```

Test layers:

- `unit`: local validation and CLI behavior;
- `contract`: exact GraphQL documents or REST routes, variables, strict wire models, transfer
  limits, mutation ambiguity, and redaction;
- `integration`: opt-in requests to local dicehub;
- `smoke`: public exports, installed wheel, console entry point, frozen executable.

Async tests use `asyncio.run()` and HTTPX async mock transports. The surface-parity test compares
all public sync and async service signatures. Representative read and mutation contract cases
cover service wiring. Focused tests cover transport lifecycle, cancellation, run polling, and
binary transfer behavior without duplicating the complete synchronous contract matrix.

## Keep test coverage focused

Test each shared input validator with its full set of input classes in one place. At other public
methods that use that exact validator, keep one invalid-input case per argument to prove validation
occurs before HTTP. Keep separate boundary cases when an argument changes the validator's behavior,
such as storage rejecting an empty path while resource listing allows the data root.

Do not remove a test merely because it reaches the same lines as another test. Credential mode,
mutation ambiguity, response redaction, pagination progress, cancellation, time limits, and partial
file writes have distinct failure conditions. Sync and async implementations also need separate
runtime checks even when their signatures match.

Public export identities and enum values are checked by source tests. The installed-wheel check
owns package isolation, installed version, typing marker, public domain imports, and CLI registration.
Its command table replaces repeated wheel `--help` calls in CI. Frozen executable checks remain
separate because bundling can fail independently of wheel installation.

One unit test checks registered options across the complete CLI command tree for credential and URL
flags. Representative group and command `--help` tests check rendering. Keep argument rejection and
credential redaction tests for commands that handle them.

The shared status mapper has focused tests for success, missing errors, authentication errors, and
redaction. Contract tests keep one failed-status case for each endpoint. For mutations, test all
transport and response failure types on one operation per service helper, then keep transport and
malformed-response cases on the other operations. Every mutation case must still check that the
request was sent once and that the error exposes no server details.

`scripts/check_docs.py` owns relative file-link validation. Source-text searches for forbidden
function names do not prove runtime safety and are not a substitute for behavior tests.

## Live tests

Live tests require `DICEHUB_LIVE_TEST=1`. Mutating tests require their additional explicit opt-in
and must clean up only resources they created. The read-run lifecycle uses
`DICEHUB_LIVE_RUN_API_KEY_DISCOVERY_TEST=1`; it mutates only a temporary managed key and reuses an
existing run. See the [managed API-key test guide](../guides/managed-api-keys.md).

`tests/integration/test_live_templates.py` is read-only and needs only `DICEHUB_LIVE_TEST=1` plus
an environment-provided API key or session cookie. It resolves the stable snappyHexMesh route,
checks the returned immutable ID, and confirms that the same record appears through filtered list
discovery. Override `DICEHUB_LIVE_TEMPLATE_ROUTE` only for a deployment without that template.

The discovery case in `tests/integration/test_live_groups.py` is read-only. Set
`DICEHUB_LIVE_GROUP_ID` to one immutable group ID visible to the configured credential. The test
resolves that group by ID and route and confirms that filtered list discovery returns the same
identity. Set `DICEHUB_LIVE_GROUP_API_KEY_UPDATE_TEST=1` to also run the mutating API-key case. It
changes the selected group's name through the SDK and CLI, then restores the original name.
Set `DICEHUB_LIVE_GROUP_MANAGEMENT_TEST=1` with session-cookie authentication to run the complete
managed-key lifecycle. That case creates and deletes its own group, subgroup, API key, avatar, and
memberships.

The app-membership lifecycle needs `DICEHUB_LIVE_APP_MEMBERSHIP_TEST=1`, a session cookie, and an
explicit `DICEHUB_LIVE_APP_TEMPLATE_ID`. It creates one private project and app, removes its exact
direct membership in `finally`, and then deletes the exact project ID.

The run-mutation lifecycle is intentionally separate because it can consume quota, incur charges,
transactionally replace the configuration's previous terminal run, and leave a stopped run in
history. It requires `DICEHUB_LIVE_RUN_API_KEY_MUTATION_TEST=1` plus explicit project, app, config,
and machine-type IDs; see the same guide before enabling it.

The controlled-cube lifecycle creates and later deletes a complete private project, starts the
server-owned conversion and domain-setup runs plus one local OpenFOAM run, and downloads the mesh
result ZIP. It requires both `DICEHUB_LIVE_TEST=1` and
`DICEHUB_LIVE_CONTROLLED_CUBE_TEST=1`, plus an explicitly configured managed key. The example
resolves the stable snappyHexMesh template route itself. See the
[controlled cube guide](../guides/controlled-cube-workflow.md) before enabling it; the standard
suite skips it.

The OpenFOAM Case Run lifecycle creates one private app in an existing project, uploads the bundled
case, starts one potentially charged run, downloads its result ZIP, and deletes the app after the
download succeeds. It requires `DICEHUB_LIVE_TEST=1`,
`DICEHUB_LIVE_OPENFOAM_CASE_RUN_TEST=1`, and the explicit project and machine values from the
[OpenFOAM Case Run guide](../guides/openfoam-case-run.md). Failure cleanup also requires `STOP_RUN`.
Set `DICEHUB_URL` only when the test must target a non-hosted deployment. The standard suite skips
the paid run.

The Wildkatze Case Run example uses a user-supplied prepared case. Its focused tests cover the
workflow, template version validation, machine selection, privacy, unknown outcomes, and result
handling. `requirements/dev.txt` includes its YAML reader and type stubs; standalone example users
install `requirements/examples.txt`. Regenerate that file from `requirements/examples.in` with
`uv pip compile --universal --python-version 3.10` when its input changes. A live test needs a small
working case, an available runner, an explicit machine and cost approval, and exact cleanup. No
Wildkatze compute is started by the standard suite.

Root-package warning: an installed-wheel smoke test must use isolated Python and assert that the
imported `dicehub.__file__` belongs to the temporary environment. Otherwise the checkout can shadow
a broken wheel.

The build command creates a source distribution, then builds the wheel from that archive. The
package check requires one wheel and one source archive for `VERSION` in `dist/`, license and typing
metadata, and an explicit set of source files. Move older build output out of `dist/` before building.
The documentation check validates frontmatter and relative file links without network access. The
README renderer uses the same Markdown renderer as PyPI and fails when the package description
cannot produce valid HTML.

Check an installed wheel in a new environment:

```bash
python -m venv /tmp/dicehub-wheel-smoke
/tmp/dicehub-wheel-smoke/bin/pip install --requirement requirements/requirements.txt
/tmp/dicehub-wheel-smoke/bin/pip install --no-deps dist/*.whl
/tmp/dicehub-wheel-smoke/bin/pip check
/tmp/dicehub-wheel-smoke/bin/python -I tests/smoke/installed_package.py VERSION
```

Use a fresh temporary directory for each run. `-I` prevents the checkout from masking a broken
installed package.

PyInstaller smoke is platform-specific. Build a one-file executable with distribution metadata:

```bash
PYINSTALLER_CONFIG_DIR=build/pyinstaller/cache python -m PyInstaller \
  --clean --noconfirm --onefile --copy-metadata dicehub-python --name dicehub \
  --distpath build/pyinstaller/dist --workpath build/pyinstaller/work \
  --specpath build/pyinstaller dicehub/__main__.py
python tests/smoke/executable.py build/pyinstaller/dist/dicehub
```

GitLab CI runs the full gate on CPython 3.10 and compatibility tests on CPython 3.11 through 3.14
on Linux. The standalone executable check uses Python 3.10 on Linux. Other operating systems and
executable platforms require their own validation before support is claimed. GitHub is a source
mirror and does not run CI.

API-key listing contract coverage assembles a result larger than 64 KiB from individually bounded
20-record responses. It also pins exclusive numeric cursors, strict descending order, duplicate and
non-progress rejection, the 10,000-key aggregate cap, and the 501-request ceiling.
