# Security policy

## Supported versions

Security fixes target the latest SDK release. Upgrade before checking whether an issue still
occurs. Older releases do not have a separate maintenance guarantee.

## Report a vulnerability

Do not report a suspected vulnerability through a public issue or pull request. Contact
[dicehub support](https://dicehub.com/contact-us), identify the request as an SDK security report,
and ask for a private channel. Do not send reproduction details through the initial support form.
There is no guaranteed response time.

After dicehub support provides a private channel, include:

- the SDK and Python versions;
- the dicehub server version, when known;
- the affected public method or CLI command;
- the authentication mode, without the credential;
- the expected and actual behavior;
- the potential impact; and
- a small reproduction that uses synthetic data.

Do not include API keys, session cookies, private case files, or server response bodies.

## Exposed credentials

If an API key may have been exposed, revoke it immediately and create a replacement in
[API-key settings](https://dicehub.com/settings/tokens). See [Managed API keys](docs/api-keys.md)
for the replacement procedure. For an exposed session cookie, request recovery instructions from
dicehub support and never include the cookie in the report.

## SDK security boundaries

The SDK binds credentials to one configured origin, verifies TLS, and rejects redirects. API keys
and session cookies are mutually exclusive. Mutations are not retried automatically. See
[authentication](docs/authentication.md), [errors](docs/errors.md), and
[resource transfer limits](docs/resources.md) for the supported boundaries.
