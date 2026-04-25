# ADR 005 — User state preserved across re-harvest (`immutable_on_match`)

**Status:** Accepted

## Context

`PatternLibraryEntry` rows are written by an automatic harvest process at the end of every realization round (M5d-1). The natural key is `(source_candidate_id, pattern_type)`; the harvest does an upsert.

Most fields on the row come from the source arrangement and should refresh on each harvest — chord symbols, tags, success metrics. Some fields, however, encode user intent that the system has no business overwriting:

- `is_curated` / `curated_at` (M5d-3) — set when the user stars an arrangement. A subsequent re-harvest must not silently revert this to `false`.
- `deleted_at` is the inverse case: when the user soft-deletes a row, a re-harvest of the same arrangement should resurrect it (clearing `deleted_at`). That's an intentional UX choice — re-harvesting is functionally an "undo delete."

If we used a naive `MERGE ... ON MATCH SET p += $props`, the Pydantic defaults for `is_curated=False, curated_at=None` would clobber whatever the user had set.

## Decision

The upsert in `PatternLibraryRepo.upsert` declares an `immutable_on_match` tuple of property names. Fields in this tuple are **excluded from `$props`** before the merge, so `ON MATCH SET p += $props` cannot touch them:

```python
immutable_on_match = (
    "id", "source_candidate_id", "pattern_type", "created_at",
    "is_curated", "curated_at",
)
```

The first four are natural-key / creation-audit fields that have always been excluded. The last two are the M5d-3 additions for user curation.

`ON CREATE` explicitly sets `is_curated = false, curated_at = null` so that new nodes start in a known state — necessary because Neo4j is schemaless and properties not in `$props` would otherwise be NULL.

`deleted_at` is intentionally **not** in the immutable list; `ON MATCH SET p.deleted_at = NULL` is unconditional, which is the resurrection-on-re-harvest behavior we want.

## Consequences

**Positive:**
- User curation survives an arbitrary number of re-harvest cycles.
- Adding a new "user state" field means appending one entry to the tuple; the pattern is consistent.
- The behavior is pinned by an integration test (`test_upsert_on_match_preserves_curation_fields`) that mutates the DB directly and re-runs the upsert.

**Negative:**
- The asymmetry between `is_curated` (preserved) and `deleted_at` (cleared) is non-obvious from the upsert query alone. Both behaviors are documented inline; tests cover both.
- A future contributor adding a new user-state field has to remember to update both `immutable_on_match` and the `ON CREATE SET` defaults. The integration test is the safety net — if they forget, it fails immediately.

## Revisit if

We add per-user state (multi-tenancy). Then the field set might split — some immutable per user, some recomputed per harvest based on the requesting user. Not a current concern (single-operator, [ADR-010](./010-no-authentication.md)).

## See also

- `backend/src/explorator/graph/pattern_library_repo.py` (the upsert)
- `backend/tests/integration/test_pattern_library_repo.py::test_upsert_on_match_preserves_curation_fields`
- ADR [003](./003-event-log-plus-denormalized-cache.md) — the broader pattern this is one instance of
