# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected credential leak, unsafe
upload retry, cookie disclosure, or command-injection issue. Report it privately
through the repository's GitHub Security Advisories feature when enabled, or
contact the maintainers through the repository owner account.

Include reproduction steps, affected versions, and the minimum evidence needed
to confirm the issue. Do not include real API keys, passwords, browser cookies,
Instagram sessions, or private media.

## Credential handling

Ziv expects credentials to remain in local configuration. The setup wizard
redacts secrets in previews, writes `.env` with owner-only permissions where
supported, and never reads cookie contents during metadata validation.

Users should keep `.env`, cookies, `.ig_session`, output, and `.ziv-state`
outside public archives and issue attachments.
