# Contributing to dicehub

## Report a bug

Use the [GitHub issue tracker](https://github.com/dicehub/dicehub-python/issues) for public bug
reports. Include:

- the SDK, Python, and operating system versions;
- the dicehub server version, when known;
- the command or public SDK method;
- the authentication mode, without the credential;
- the expected and actual results; and
- a small reproduction that uses synthetic data.

Remove credentials, private project data, and server response bodies. Follow the
[security policy](SECURITY.md) for a suspected vulnerability. For account or service problems,
contact [dicehub support](https://dicehub.com/contact-us).

## Propose a change

GitLab is the source repository and runs CI. GitHub is a public source mirror. If you do not have
access to the private GitLab repository, contact [dicehub support](https://dicehub.com/contact-us),
describe the proposed change, and request patch-submission instructions before sending code or
files. Ask maintainers to review changes that are substantial or affect public interfaces before
implementation.

Contributors with GitLab access should use a small branch and a Conventional Commit title such as
`fix: validate a resource cursor`. Target `dev` in a draft merge request. Describe the problem,
changed behavior, and verification results, and keep unrelated changes separate.

## Set up development

Use one supported CPython version from 3.10 through 3.14 and the pinned development requirements.
GitLab CI checks every supported Python version. From the repository root:

```bash
uv venv
source .venv/bin/activate
uv pip install --requirement requirements/dev.txt
uv pip install --no-build-isolation --no-deps --editable .
```

Read the [architecture](docs/development/architecture.md) before changing a service. Keep public
sync and async methods consistent. The CLI calls the public SDK; it does not implement separate
API behavior. Add a focused regression test for a bug and update documentation for public changes.

## Verify a change

Run the [full verification gate](docs/development/testing.md) before submitting a change. Tests
run locally without a dicehub server unless live tests are explicitly enabled. Never enable live
mutation tests against a shared deployment without the owner's permission.

Keep discussions respectful and technical. Do not post personal information or credentials.
