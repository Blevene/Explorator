# Security Policy

## Supported versions

There are no tagged releases yet. Security fixes land on the `main` branch, which
is the only supported line — please report against, and update to, the latest
`main` (a commit SHA is the most precise way to reference a version).

## Reporting a vulnerability

If you discover a security issue, please report it privately through [GitHub private vulnerability reporting](https://github.com/Blevene/Explorator/security/advisories/new) (the **Report a vulnerability** button on the repository's Security tab) instead of opening a public GitHub issue or pull request. Include a description of the issue, the affected version (commit SHA is fine), and a minimal reproduction if you have one.

You should expect a response within a few business days. We don't operate a bug bounty program, but we appreciate responsible disclosure and will credit reporters in the fix's commit message and any release notes if you'd like.

## Scope

This repository is a single-tenant local-first music tool. There is no authentication or authorization layer (see [ADR-010](./docs/decisions/010-no-authentication.md)) — the assumption is that the API is bound to localhost during normal use. Issues that exclusively rely on operating the backend on a public network without an upstream auth layer are out of scope; documenting that assumption more loudly is in scope.

In-scope examples: prompt-injection paths that escape into stored data; Cypher injection via genre/session inputs; arbitrary file write via the genre approve flow; secrets leaking through logs or SSE streams; supply-chain advisories on first-party dependencies.
