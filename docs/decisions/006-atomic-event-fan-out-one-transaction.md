# ADR 006 — Atomic event + fan-out in one Neo4j transaction

**Status:** Accepted

## Context

A single user action — clicking a star to curate an arrangement — produces several writes:

1. Create a `UserFeedbackEvent` node (the audit log).
2. Create the `(Session)-[:HAS_FEEDBACK]->(event)` edge.
3. Create the `(event)-[:ABOUT]->(arrangement)` edge.
4. `SET is_curated, curated_at` on every non-deleted facet row in the pattern library that shares the arrangement's `source_candidate_id` (1–5 rows).

If any subset of these succeeds, we have a torn write. The audit log without the denormalized state means the next page-load shows stale curation. The denormalized state without the event means the audit history is wrong.

Two paths to atomicity:

1. **Auto-commit each write, accept eventual consistency.** Use idempotency to clean up partial writes on the next request. Cheap to implement, hard to reason about.
2. **Multi-statement transaction.** Open one transaction, run all four writes, commit or rollback together.

Neo4j's bolt driver supports explicit transactions via `await session.begin_transaction()`. Multiple `tx.run(...)` calls share the transaction; `tx.commit()` makes them durable as a unit.

## Decision

**Use one explicit transaction for any composite operation that has dependent writes.**

The canonical example is `curation_service.curate_arrangement` (in `backend/src/explorator/services/pattern_library/curation_service.py`):

```python
async with driver.session() as neo_session:
    tx = await neo_session.begin_transaction()
    try:
        # Probe: resolve session_id, count matching pattern rows
        # 404 / 409 raised here BEFORE any writes, with rollback
        ...
        # Writes:
        await tx.run("CREATE (e:UserFeedbackEvent $props)", props=event_props)
        await tx.run("MATCH (s:Session {id: $sid}), (e:UserFeedbackEvent {id: $eid}) "
                     "CREATE (s)-[:HAS_FEEDBACK]->(e)", ...)
        await tx.run("MATCH (e:UserFeedbackEvent {id: $eid}), (a:ArrangementCandidate {id: $aid}) "
                     "CREATE (e)-[:ABOUT]->(a)", ...)
        await tx.run(CURATION_FANOUT_CYPHER, ...)
        await tx.commit()
    except Exception:
        if not tx.closed():
            await tx.rollback()
        raise
```

**The probe runs inside the transaction**, not before it. This was originally a two-phase design (read probe in auto-commit, then open tx for writes); review found a TOCTOU window where a concurrent soft-delete between probe and commit could leak partial state. Moving the probe inside the tx eliminates the window.

**Shared Cypher constants prevent drift** when the same query needs to run from multiple call-sites (e.g. the curation fan-out is also exposed as a standalone `PatternLibraryRepo.toggle_curation` method for test seeding). `CURATION_FANOUT_CYPHER` lives as a module constant in `pattern_library_repo.py` and is imported by the service.

The cascade-delete in `DELETE /v1/sessions/{id}` follows the same pattern (three DETACH DELETE statements in one tx).

## Consequences

**Positive:**
- Audit log and denormalized state cannot drift — they commit together or both roll back.
- The 404 / 409 / 422 status discrimination happens before any writes, so failed validation never leaves orphan state.
- Pattern is replicable — curation, cascade delete, future composite operations all use the same shape.

**Negative:**
- A bit of boilerplate per service (`begin_transaction` / `try` / `commit` / `rollback`). Could be wrapped in a context manager helper if it accumulates further.
- Long-running transactions hold locks; if a Cypher statement inside the tx is slow, it stalls other writes. None of our composite ops do anything slow inside the tx; the probe is a fast indexed lookup.

## Revisit if

We start needing distributed transactions (cross-store writes, ADR-001 inverted). At that point we'd reach for the saga pattern and accept eventual consistency on cross-store boundaries.

## See also

- `backend/src/explorator/services/pattern_library/curation_service.py` (canonical implementation)
- `backend/src/explorator/api/routes/sessions.py:delete_session` (cascade-delete using the same pattern)
- ADR [003](./003-event-log-plus-denormalized-cache.md) — the dual-write pattern this enforces atomicity for
