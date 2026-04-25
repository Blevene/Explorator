# Architectural Decision Records

Lightweight ADRs for the load-bearing decisions in Explorator. Each one captures *why* we chose what we chose, not just what we chose.

Format follows the [Michael Nygard template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions): Title, Status, Context, Decision, Consequences.

These exist for two reasons:

1. **Future-you onboarding** — six months from now, "why is `is_curated` denormalized rather than derived from the event log?" should be a 30-second answer, not an archaeology dig through commit messages.
2. **Defending against drift** — when a refactor proposal would invert a decision recorded here, the ADR forces a deliberate "supersede" rather than a quiet erosion.

## Index

| # | Title | Status |
|---|---|---|
| [001](./001-neo4j-single-source-of-truth.md) | Neo4j as the single source of truth | Accepted |
| [002](./002-langgraph-orchestration-pure-domain.md) | LangGraph for orchestration; pure Python for domain | Accepted |
| [003](./003-event-log-plus-denormalized-cache.md) | Append-only event log + denormalized read cache | Accepted |
| [004](./004-provenance-first-class.md) | Provenance is first-class on every candidate | Accepted |
| [005](./005-user-state-preserved-across-re-harvest.md) | User state preserved across re-harvest (`immutable_on_match`) | Accepted |
| [006](./006-atomic-event-fan-out-one-transaction.md) | Atomic event + fan-out in one Neo4j transaction | Accepted |
| [007](./007-optimistic-ui-with-rollback.md) | Optimistic UI with server reconciliation and rollback | Accepted |
| [008](./008-css-custom-properties-design-tokens.md) | CSS custom properties + `designTokens.ts` for the palette | Accepted |
| [009](./009-isolated-test-neo4j.md) | Isolated test Neo4j container with autouse cleanup | Accepted |
| [010](./010-no-authentication.md) | No authentication — single-operator local tool | Accepted |

## Adding a new ADR

```bash
# 1. Number it sequentially
NEXT=$(ls docs/decisions/[0-9]*.md | wc -l)
NEXT=$(printf "%03d" $((NEXT + 1)))

# 2. Create the file
touch "docs/decisions/${NEXT}-short-kebab-title.md"

# 3. Add a row to the index above
```

If you're superseding a previous decision, set the previous one's status to `Superseded by NNN` and link it from the new ADR's Context section.

## What belongs here

A decision is ADR-worthy if reversing it would touch multiple subsystems, force a data migration, or invalidate a non-trivial chunk of the codebase. If it's local to one file or class, it's a code comment, not an ADR.

What does NOT belong here:
- Per-milestone designs — those live in [`docs/superpowers/specs/`](../superpowers/specs/)
- Code-level patterns enforced by lint/types — those should be enforced, not documented
- Personal preferences — those go in `~/.claude/projects/.../memory/feedback_*.md`
