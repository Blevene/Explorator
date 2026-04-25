# ADR 003 — Append-only event log + denormalized read cache

**Status:** Accepted

## Context

User actions that change durable state — submitting feedback, curating a finalist — need two things from us:

1. **Authoritative history.** Why did this candidate's score change? Did the user star this arrangement, then unstar it? When? The event sequence has to be recoverable, both for debugging and for future taste-model training.
2. **Fast filter queries.** `/patterns?curated_only=true` should return in tens of milliseconds against a library of thousands of patterns, without an aggregating subquery per row.

Two pure approaches:

1. **Event log only.** `is_curated` for a pattern = the last `pattern_curation` event whose `candidate_id` matches the pattern's `source_candidate_id`. Beautifully simple, correct by construction. But every list query becomes a correlated max-aggregation per row.
2. **State only.** Just write `is_curated` directly; no event. Fast queries. But you've lost history: can't tell when, can't tell whether the user oscillated, can't train on it later.

## Decision

**Both.** For state that has user-visible history value, we dual-write:

- An append-only `UserFeedbackEvent` node — never mutated, only created.
- A denormalized property on the affected row(s) (e.g. `is_curated` / `curated_at` on `PatternLibraryEntry`) — a read cache.

The two writes happen inside one Neo4j transaction ([ADR-006](./006-atomic-event-fan-out-one-transaction.md)). The event log is authoritative; the denormalized property is a cache.

Concrete instances of this pattern:

| Concern | Event log node | Denormalized cache |
|---|---|---|
| Pattern curation (M5d-3) | `UserFeedbackEvent(feedback_type="pattern_curation", content="curated"\|"uncurated")` | `PatternLibraryEntry.is_curated`, `curated_at` |
| Text feedback (M3b) | `UserFeedbackEvent(feedback_type="text_reaction", interpreted_adjustments, weight_deltas)` | `ObjectiveWeights` snapshot per session |

## Consequences

**Positive:**
- Filter queries (`WHERE p.is_curated = true`) hit a property and an index — fast.
- The audit log is intact and queryable: "show me every curation event for this session, in order" is a one-liner.
- Future taste-model training has a clean event stream to consume without reverse-engineering current state.
- The `feedback_type` discriminator on `UserFeedbackEvent` lets new event types layer in without a new label.

**Negative:**
- The two writes can drift if a future caller bypasses the transaction. Mitigation: the denormalized writes only happen in services / repo methods that also write the event; documented invariant ([ADR-006](./006-atomic-event-fan-out-one-transaction.md)).
- The event log grows unboundedly (no GC). At current scale, irrelevant; if it ever matters, we can introduce a snapshot-and-truncate mechanism.

## Revisit if

We add a third class of state with similar requirements (e.g. mutation history, comparison views the user iterated on). Pattern is the same; just instantiate the same shape.

## See also

- ADR [006](./006-atomic-event-fan-out-one-transaction.md) for transaction guarantees
- ADR [005](./005-user-state-preserved-across-re-harvest.md) for the related "user state must survive automatic re-harvest" invariant
