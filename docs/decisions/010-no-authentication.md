# ADR 010 — No authentication; single-operator local tool

**Status:** Accepted

## Context

Explorator is, today, a creative tool that runs on the producer's local machine. The backend listens on `0.0.0.0:8000`, the frontend on `0.0.0.0:5173` (or whatever Vite reports). All sessions, candidates, exports, and pattern library entries belong to the operator.

A typical default for any user-facing app is "add auth from day one" — JWT, OAuth, session cookies, the works. But the cost isn't zero:

- Every endpoint needs auth middleware.
- Pydantic models split into "request" and "response" shapes around user-bound state.
- Tests need fixtures for "user A vs user B."
- The frontend gains a login flow, a token refresh dance, redirect handling.
- Every Neo4j query that today is `MATCH (s:Session ...)` becomes `MATCH (u:User)-[:OWNS]->(s:Session ...) WHERE u.id = $current_user`.

For a single-operator tool, all of that is pure tax.

## Decision

**There is no authentication.**

- All API endpoints accept any caller without challenge.
- All Neo4j queries are scoped only by `session_id`, `arrangement_id`, etc. — never by an owning user.
- The frontend never asks for a login.
- `0.0.0.0` binding is the deliberate default (per the user's standing preference) so the app is reachable from any device on the local network — useful when listening on a phone speaker or testing on a tablet, not a security stance.

The implicit security model: **the operator controls the network**. Don't expose the backend port to the public internet.

## Consequences

**Positive:**
- Everything is simpler — schemas, queries, tests, frontend flows.
- Iteration speed on features that have nothing to do with identity is fast. We've shipped M0 → M5d in weeks.
- There's no ambient dependency on an identity provider, no token expiry to debug, no "logged out" state to design around.

**Negative:**
- Cannot share the running app with a collaborator unless they trust the network the backend lives on.
- Cannot deploy to a public URL without rethinking auth.
- Multi-user features (sharing a pattern library, collaborative sessions) require this decision to be reversed first.
- Pattern library data has no per-owner partitioning — adding it later means a migration that retroactively assigns owners, which is awkward but not catastrophic at our scale.

## Revisit if

- We want to deploy to a non-trusted network or a public URL.
- We want collaborative sessions or shared pattern libraries.
- We want to publish exports to a service that needs to attribute them to a user.

When that day comes, the path is roughly:

1. Add a `User` node label and an `OWNS` relationship from `User` to `Session`.
2. Add FastAPI middleware that resolves the current user (any auth approach — JWT, OIDC, simple API key).
3. Migrate existing data to a single "default" user.
4. Update queries to filter by ownership at the boundary; domain code stays unchanged ([ADR-002](./002-langgraph-orchestration-pure-domain.md) makes this localized).

## See also

- `backend/src/explorator/api/app.py` (no auth dependencies wired)
- The `Bind Address` user feedback memory (`feedback_bind_address.md`) — the 0.0.0.0 default is intentional
