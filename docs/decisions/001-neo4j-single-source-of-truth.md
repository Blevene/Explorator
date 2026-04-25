# ADR 001 — Neo4j as the single source of truth

**Status:** Accepted

## Context

Early in the project we needed to choose how to persist sessions, candidates, arrangements, scorecards, feedback events, lineage, and the pattern library. The natural fit for the data shape was a graph: candidates have parents, arrangements derive from candidates, feedback events relate to candidates and sessions, patterns reference their source arrangement. A relational schema would express most of this as a fan-out of foreign keys plus a separate "lineage" table.

A typical default would be PostgreSQL for transactional state plus Neo4j for relationship-heavy reads — but this introduces dual-writes, two query languages, and replication concerns. For a single-operator tool with modest scale (sessions on the order of dozens of candidates), the cost of running both stores outweighs any incremental benefit.

## Decision

**Neo4j is the only persistent store.** Sessions, candidates, arrangements, scorecards, feedback events, pattern library entries, lineage, and genre profiles created by the research agent all live in Neo4j. Genre YAML files on disk are the source of truth for the seed genres (loaded into memory, not into the graph).

There is no PostgreSQL, no Redis, no S3. Exports land on the local filesystem under a configurable directory.

## Consequences

**Positive:**
- One query language (Cypher) and one driver to reason about.
- Lineage queries (provenance traces, comparison, explanation) are natural traversals rather than recursive CTEs.
- Atomic multi-statement transactions cover all our durable writes; we never have to coordinate cross-store consistency.

**Negative:**
- Some queries that would be SQL one-liners are awkward in Cypher (e.g. `LIMIT/OFFSET`-style pagination — we use keyset cursors instead).
- Neo4j's strict mode for indexes and constraints requires per-label setup; that's now centralized in `backend/src/explorator/graph/schema.py`.
- We can't reach for boring relational tools (alembic migrations, pgAdmin, foreign-key constraints) when something is awkward.

**Mitigations / conventions:**
- Migrations live under `backend/scripts/migrations/` and follow a consistent dry-run / `--yes` pattern; idempotent by design.
- Tests run against an isolated Neo4j container with autouse cleanup ([ADR-009](./009-isolated-test-neo4j.md)).

## Revisit if

We grow beyond a single operator, need multi-tenant isolation, or hit Neo4j-specific scale limits. None of these are visible on the horizon.
