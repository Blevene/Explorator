# M5d-3 Pattern Curation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit, arrangement-level user curation (star/unstar) to the pattern library, surfaced on `FinalistPanel` during a session and on `PatternCard` in the library browser, with a `Curated only` filter. Every toggle writes an append-only `UserFeedbackEvent` and updates a denormalized `is_curated` flag across all facet rows for the arrangement.

**Architecture:**
- **Backend:** Extend `PatternLibraryEntry` with `is_curated` + `curated_at`. Reuse `UserFeedbackEvent` with `feedback_type="pattern_curation"`. Curation service orchestrates event write + denormalized fan-out in a single Neo4j transaction. Arrangement API response derives curation state via a single `UNWIND` + `OPTIONAL MATCH` + `head(collect(p))` query — nullable to signal "not yet harvested."
- **Frontend:** Shared `StarButton` component, `toggleCuration` actions on `patternLibraryStore` and `arrangementStore`, `setCuratedOnly` on `patternFiltersStore`. Optimistic UI with rollback.
- **Migration:** Forward-only backfill of `is_curated=false` on existing rows + new index on `UserFeedbackEvent(feedback_type, candidate_id)`.

**Tech Stack:** FastAPI, Pydantic, Neo4j, React, Zustand, Vitest, Playwright, sonner.

**Spec:** `docs/superpowers/specs/2026-04-20-m5d3-pattern-curation-design.md`

**Branch:** `feature/m5d3-pattern-curation` (already exists; spec committed at `0bdd3fb`)

---

## Part 1 — Backend model, filter, migration

### Task 1: Add `is_curated` + `curated_at` to `PatternLibraryEntry`

**Files:**
- Modify: `backend/src/explorator/models/memory.py:34-49`
- Test: `backend/tests/unit/test_memory_models.py` (new file if absent)

- [ ] **Step 1: Write failing test**

Create or append to `backend/tests/unit/test_memory_models.py`:

```python
from explorator.models.memory import PatternLibraryEntry


def test_pattern_library_entry_curation_defaults():
    entry = PatternLibraryEntry(
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_x",
    )
    assert entry.is_curated is False
    assert entry.curated_at is None


def test_pattern_library_entry_curation_roundtrip():
    from datetime import datetime, timezone
    now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    entry = PatternLibraryEntry(
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_x",
        is_curated=True,
        curated_at=now,
    )
    payload = entry.model_dump(mode="json")
    assert payload["is_curated"] is True
    assert payload["curated_at"] == now.isoformat()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_memory_models.py -v
```
Expected: FAIL — `is_curated`/`curated_at` not on the model.

- [ ] **Step 3: Edit the model**

In `backend/src/explorator/models/memory.py`, add two fields immediately after the `deleted_at` block (line 46):

```python
    # Soft-delete tombstone. Set by soft_delete; cleared unconditionally by upsert ON MATCH.
    # Rows with deleted_at != None are invisible to list_page / get_by_id / iter_all.
    deleted_at: datetime | None = None
    # Explicit user curation (M5d-3). Preserved across re-harvest: upsert's
    # ON MATCH excludes these fields from $props. See curation_service.
    is_curated: bool = False
    curated_at: datetime | None = None
```

Also add a comment above `UserFeedbackEvent` (line 23) documenting the pattern_curation convention:

```python
class UserFeedbackEvent(BaseEntity):
    """Explicit user reaction.

    feedback_type discriminator values:
      - "text_reaction" (default, legacy) — LLM-interpreted reaction,
        populates interpreted_adjustments and weight_deltas.
      - "pattern_curation" (M5d-3) — explicit star/unstar on an arrangement.
        content = "curated" | "uncurated"; candidate_id = arrangement_id;
        interpreted_adjustments/weight_deltas unused (empty dict).
    """
```

- [ ] **Step 4: Run tests — pass**

```bash
cd backend && uv run pytest tests/unit/test_memory_models.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/memory.py backend/tests/unit/test_memory_models.py
git commit -m "feat(m5d-3): add is_curated/curated_at to PatternLibraryEntry"
```

---

### Task 2: Add `curated_only` to `PatternFilters`

**Files:**
- Modify: `backend/src/explorator/services/pattern_library/filters.py:9-12`
- Test: `backend/tests/unit/test_pattern_filters.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_pattern_filters.py`:

```python
from explorator.services.pattern_library.filters import PatternFilters


def test_pattern_filters_curated_only_default_false():
    f = PatternFilters()
    assert f.curated_only is False


def test_pattern_filters_curated_only_opt_in():
    f = PatternFilters(curated_only=True)
    assert f.curated_only is True
    assert f.genre is None
    assert f.pattern_type is None
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/unit/test_pattern_filters.py -v
```
Expected: FAIL — `curated_only` unknown field.

- [ ] **Step 3: Add the field**

Replace `backend/src/explorator/services/pattern_library/filters.py`:

```python
"""Typed filter object for PatternLibraryRepo.list_page / iter_all.

Prevents raw kwargs leaking storage concerns back into the router. Add new
filter fields here, not as positional args on repo methods.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PatternFilters:
    genre: str | None = None
    pattern_type: str | None = None
    curated_only: bool = False
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/unit/test_pattern_filters.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_library/filters.py backend/tests/unit/test_pattern_filters.py
git commit -m "feat(m5d-3): add curated_only to PatternFilters"
```

---

### Task 3: Migration script

**Files:**
- Create: `backend/scripts/migrations/m5d3_curation_fields.py`

- [ ] **Step 1: Create the migration**

Create `backend/scripts/migrations/m5d3_curation_fields.py`:

```python
"""M5d-3 migration: backfill is_curated=false on existing PatternLibraryEntry
rows and create a feedback-event filtering index.

Neo4j is schemaless; new writes carry `is_curated` / `curated_at` via model
defaults. This script only matters for pre-existing rows harvested before
M5d-3 landed — they need `is_curated=false` set explicitly so
`WHERE p.is_curated = true` filter queries behave correctly.

Idempotent (IF NOT EXISTS + IS NULL guards).

Usage:
    # Preview.
    uv run python scripts/migrations/m5d3_curation_fields.py

    # Apply.
    uv run python scripts/migrations/m5d3_curation_fields.py --yes
"""
import argparse
import asyncio
import os
import sys

from explorator.graph.connection import get_driver


BACKFILL_CYPHER = """
MATCH (p:PatternLibraryEntry)
WHERE p.is_curated IS NULL
SET p.is_curated = false
RETURN count(p) AS updated
"""

INDEX_CYPHER = """
CREATE INDEX user_feedback_event_type IF NOT EXISTS
  FOR (n:UserFeedbackEvent) ON (n.feedback_type, n.candidate_id)
"""


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d3-curation] Target Neo4j: {uri}")
    if not apply:
        print("[m5d3-curation] Dry-run. Would execute:")
        print(BACKFILL_CYPHER)
        print(INDEX_CYPHER)
        return 0

    driver = await get_driver()
    try:
        async with driver.session() as neo_session:
            result = await neo_session.run(BACKFILL_CYPHER)
            record = await result.single()
            updated = record["updated"] if record else 0
            print(f"[m5d3-curation] Backfilled is_curated=false on {updated} rows.")
            await neo_session.run(INDEX_CYPHER)
            print("[m5d3-curation] Created index user_feedback_event_type (if not exists).")
        return 0
    finally:
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
```

- [ ] **Step 2: Dry-run smoke-test**

```bash
cd backend && uv run python scripts/migrations/m5d3_curation_fields.py
```
Expected: prints Cypher, exits 0. Does not connect to Neo4j.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrations/m5d3_curation_fields.py
git commit -m "feat(m5d-3): migration to backfill is_curated and index feedback events"
```

---

## Part 2 — `PatternLibraryRepo` changes

### Task 4: Upsert regression — preserve curation fields across re-harvest

**Files:**
- Modify: `backend/src/explorator/graph/pattern_library_repo.py:38` (immutable list)
- Test: `backend/tests/integration/test_pattern_library_repo.py` (append)

This is the load-bearing invariant from the spec: a user's "I liked this" must survive re-harvest. Test-first.

- [ ] **Step 1: Write failing regression test**

Append to `backend/tests/integration/test_pattern_library_repo.py`:

```python
import pytest
from datetime import datetime, timezone

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now


def _curated_entry(**overrides):
    defaults = dict(
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_curate_preserve",
        success_metrics={"weighted_total": 0.8},
    )
    defaults.update(overrides)
    return PatternLibraryEntry(**defaults)


@pytest.mark.asyncio
async def test_upsert_on_match_preserves_curation_fields(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    # First harvest.
    entry = _curated_entry()
    await repo.upsert(entry)
    # Simulate user curation by mutating state directly (the repo.toggle_curation
    # method lands in Task 5; this test pins the upsert invariant independently).
    curated_at = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
    async with neo4j_driver.session() as s:
        await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) "
            "SET p.is_curated = true, p.curated_at = $ts",
            scid=entry.source_candidate_id, pt=entry.pattern_type,
            ts=curated_at.isoformat(),
        )
    # Re-harvest — Pydantic default is_curated=False must NOT wipe curation.
    reharvested = _curated_entry(success_metrics={"weighted_total": 0.9})
    await repo.upsert(reharvested)

    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at, "
            "       p.weighted_total AS weighted_total",
            scid=entry.source_candidate_id, pt=entry.pattern_type,
        )
        record = await result.single()
    assert record["is_curated"] is True, "curation cleared by re-harvest"
    assert record["curated_at"] == curated_at.isoformat()
    assert record["weighted_total"] == pytest.approx(0.9)  # new metrics did land


@pytest.mark.asyncio
async def test_upsert_on_create_defaults_curation(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    entry = _curated_entry(source_candidate_id="cand_create_default")
    await repo.upsert(entry)
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=entry.source_candidate_id,
        )
        record = await result.single()
    assert record["is_curated"] is False
    assert record["curated_at"] is None
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py::test_upsert_on_match_preserves_curation_fields -v
```
Expected: FAIL — `is_curated` gets cleared because it's in `$props`.

- [ ] **Step 3: Extend the immutable-on-match tuple**

In `backend/src/explorator/graph/pattern_library_repo.py:38`, change:

```python
        immutable_on_match = ("id", "source_candidate_id", "pattern_type", "created_at")
```

to:

```python
        # On re-harvest, these fields must survive untouched:
        #   id/scid/pt/created_at — natural key + creation audit
        #   is_curated/curated_at — explicit user intent (M5d-3), would otherwise
        #                           be wiped by the Pydantic default (False/None).
        immutable_on_match = (
            "id", "source_candidate_id", "pattern_type", "created_at",
            "is_curated", "curated_at",
        )
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py -v
```
Expected: all pass (pre-existing + new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/integration/test_pattern_library_repo.py
git commit -m "feat(m5d-3): preserve is_curated/curated_at across re-harvest"
```

---

### Task 5: `PatternLibraryRepo.toggle_curation()`

**Files:**
- Modify: `backend/src/explorator/graph/pattern_library_repo.py` (append method)
- Test: `backend/tests/integration/test_pattern_library_repo.py` (append)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/integration/test_pattern_library_repo.py`:

```python
@pytest.mark.asyncio
async def test_toggle_curation_updates_all_facets(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_multi"
    # Seed 3 facets for the same arrangement.
    for ptype in ("progression", "voicing", "bass"):
        await repo.upsert(_curated_entry(source_candidate_id=scid, pattern_type=ptype))
    now = datetime(2026, 4, 24, 13, 0, tzinfo=timezone.utc)

    affected = await repo.toggle_curation(arrangement_id=scid, is_curated=True, now=now)

    assert len(affected) == 3
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.id AS id, p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=scid,
        )
        rows = await result.data()
    assert all(r["is_curated"] is True for r in rows)
    assert all(r["curated_at"] == now.isoformat() for r in rows)


@pytest.mark.asyncio
async def test_toggle_curation_uncurate_clears_curated_at(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_uncurate"
    await repo.upsert(_curated_entry(source_candidate_id=scid))
    await repo.toggle_curation(
        arrangement_id=scid, is_curated=True,
        now=datetime(2026, 4, 24, 13, 0, tzinfo=timezone.utc),
    )
    affected = await repo.toggle_curation(
        arrangement_id=scid, is_curated=False,
        now=datetime(2026, 4, 24, 13, 5, tzinfo=timezone.utc),
    )
    assert len(affected) == 1
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=scid,
        )
        record = await result.single()
    assert record["is_curated"] is False
    assert record["curated_at"] is None


@pytest.mark.asyncio
async def test_toggle_curation_skips_soft_deleted(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_softdel"
    await repo.upsert(_curated_entry(source_candidate_id=scid, pattern_type="progression"))
    await repo.upsert(_curated_entry(source_candidate_id=scid, pattern_type="voicing"))

    # Soft-delete one facet.
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: 'voicing'}) "
            "RETURN p.id AS id",
            scid=scid,
        )
        deleted_id = (await result.single())["id"]
    await repo.soft_delete(deleted_id)

    affected = await repo.toggle_curation(
        arrangement_id=scid, is_curated=True, now=utc_now(),
    )
    assert len(affected) == 1
    assert deleted_id not in affected


@pytest.mark.asyncio
async def test_toggle_curation_empty_arrangement_returns_empty(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    affected = await repo.toggle_curation(
        arrangement_id="cand_nonexistent", is_curated=True, now=utc_now(),
    )
    assert affected == []
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py -v -k toggle
```
Expected: FAIL — `toggle_curation` doesn't exist.

- [ ] **Step 3: Add the method**

Append to `backend/src/explorator/graph/pattern_library_repo.py` (after `soft_delete`):

```python
    async def toggle_curation(
        self,
        *,
        arrangement_id: str,
        is_curated: bool,
        now: "datetime",
    ) -> list[str]:
        """Flip is_curated on every non-deleted facet row for an arrangement.

        Fan-out semantics: one arrangement → 1–5 facet rows. Returns the IDs
        of the rows that were updated. Empty list means no matching non-deleted
        rows exist (caller translates to HTTP 409).

        When is_curated=False, curated_at is cleared to NULL.
        """
        query = """
        MATCH (p:PatternLibraryEntry {source_candidate_id: $aid})
        WHERE p.deleted_at IS NULL
        SET p.is_curated = $is_curated,
            p.curated_at = CASE WHEN $is_curated THEN $now ELSE NULL END
        RETURN p.id AS id
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(
                query,
                aid=arrangement_id,
                is_curated=is_curated,
                now=now.isoformat(),
            )
            records = [r async for r in result]
        return [r["id"] for r in records]
```

Also add `from datetime import datetime` to the imports at the top of the file if not present.

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/integration/test_pattern_library_repo.py
git commit -m "feat(m5d-3): add PatternLibraryRepo.toggle_curation"
```

---

### Task 6: `list_page` / `iter_all` honor `curated_only`

**Files:**
- Modify: `backend/src/explorator/graph/pattern_library_repo.py:104-177`
- Test: `backend/tests/integration/test_pattern_library_repo.py` (append)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/integration/test_pattern_library_repo.py`:

```python
from explorator.services.pattern_library.filters import PatternFilters


@pytest.mark.asyncio
async def test_list_page_curated_only_filter(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    # Seed: one curated arrangement, one uncurated.
    for scid, curate in (("cand_filter_c1", True), ("cand_filter_c2", False)):
        await repo.upsert(_curated_entry(
            source_candidate_id=scid, pattern_type="progression",
        ))
        if curate:
            await repo.toggle_curation(
                arrangement_id=scid, is_curated=True, now=utc_now(),
            )

    # curated_only=False → both visible.
    all_items, _ = await repo.list_page(filters=PatternFilters(), limit=50)
    ids_all = {e["source_candidate_id"] for e in all_items}
    assert "cand_filter_c1" in ids_all
    assert "cand_filter_c2" in ids_all

    # curated_only=True → only curated.
    curated_items, _ = await repo.list_page(
        filters=PatternFilters(curated_only=True), limit=50,
    )
    ids_curated = {e["source_candidate_id"] for e in curated_items}
    assert "cand_filter_c1" in ids_curated
    assert "cand_filter_c2" not in ids_curated
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py::test_list_page_curated_only_filter -v
```
Expected: FAIL — filter ignored; both rows returned.

- [ ] **Step 3: Thread the filter into both queries**

In `backend/src/explorator/graph/pattern_library_repo.py`, update `list_page`'s `params` and `query` (lines 118-137):

```python
        filters = filters or PatternFilters()
        params: dict[str, Any] = {
            "genre": filters.genre,
            "ptype": filters.pattern_type,
            "curated_only": filters.curated_only,
            "after_score": cursor.after_score if cursor else None,
            "after_id": cursor.after_id if cursor else None,
            "limit": limit + 1,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
          AND (NOT $curated_only OR p.is_curated = true)
          AND ($after_score IS NULL
               OR p.weighted_total < $after_score
               OR (p.weighted_total = $after_score AND p.id > $after_id))
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        LIMIT $limit
        """
```

Update `iter_all` (lines 164-173) similarly:

```python
        filters = filters or PatternFilters()
        params: dict[str, Any] = {
            "genre": filters.genre,
            "ptype": filters.pattern_type,
            "curated_only": filters.curated_only,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
          AND (NOT $curated_only OR p.is_curated = true)
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        """
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py -v
```
Expected: all pass.

- [ ] **Step 5: Add cursor-stability test**

Append:

```python
@pytest.mark.asyncio
async def test_list_page_cursor_stable_across_curated_only_toggle(neo4j_driver):
    """Cursor emitted under one filter regime is still valid under the other.

    The cursor encodes (weighted_total, id) only; it does not embed the filter
    set, so paginating with the same cursor across a filter toggle must just
    re-apply the new filter — never 500 or produce inconsistent ordering.
    """
    repo = PatternLibraryRepo(neo4j_driver)
    # Seed 6 entries, alternating curated/uncurated, strictly-descending score.
    for i in range(6):
        scid = f"cand_cursor_{i}"
        await repo.upsert(_curated_entry(
            source_candidate_id=scid,
            pattern_type="progression",
            success_metrics={"weighted_total": 0.9 - (i * 0.1)},
        ))
        if i % 2 == 0:
            await repo.toggle_curation(
                arrangement_id=scid, is_curated=True, now=utc_now(),
            )

    # Page 1 with no filter → 2 items, cursor returned.
    items1, cursor1 = await repo.list_page(
        filters=PatternFilters(), limit=2,
    )
    assert cursor1 is not None
    assert len(items1) == 2

    # Page 2 with curated_only=True using the same cursor → no crash, only
    # curated items that come AFTER the cursor returned.
    items2, _ = await repo.list_page(
        filters=PatternFilters(curated_only=True), cursor=cursor1, limit=10,
    )
    assert all(i["is_curated"] is True for i in items2)
```

- [ ] **Step 6: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_pattern_library_repo.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/integration/test_pattern_library_repo.py
git commit -m "feat(m5d-3): honor curated_only filter in list_page and iter_all"
```

---

## Part 3 — Arrangement curation derivation

### Task 7: `ArrangementCandidateRepo.fetch_curation_state()`

Spec §"GET on arrangement endpoints" requires a single-round-trip LEFT-JOIN derivation — no N+1.

**Files:**
- Modify: `backend/src/explorator/graph/arrangement_candidate_repo.py`
- Test: `backend/tests/integration/test_arrangement_curation_derivation.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/integration/test_arrangement_curation_derivation.py`:

```python
import pytest
from datetime import datetime, timezone

from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now


async def _seed_arrangement(driver, arr_id, session_id="sess_test"):
    async with driver.session() as s:
        await s.run(
            "MERGE (a:ArrangementCandidate {id: $id}) "
            "SET a.session_id = $sid, a.weighted_total = 0.5",
            id=arr_id, sid=session_id,
        )


async def _seed_pattern(repo, arr_id, ptype="progression"):
    await repo.upsert(PatternLibraryEntry(
        pattern_type=ptype, genre="jazz",
        source_candidate_id=arr_id,
        success_metrics={"weighted_total": 0.8},
    ))


@pytest.mark.asyncio
async def test_fetch_curation_state_uncurated(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_u")
    await _seed_pattern(pl, "arr_deriv_u")

    state = await ac.fetch_curation_state(["arr_deriv_u"])
    assert state == {"arr_deriv_u": (False, None)}


@pytest.mark.asyncio
async def test_fetch_curation_state_curated(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_c")
    await _seed_pattern(pl, "arr_deriv_c")
    curated_at = datetime(2026, 4, 24, 14, 0, tzinfo=timezone.utc)
    await pl.toggle_curation(arrangement_id="arr_deriv_c", is_curated=True, now=curated_at)

    state = await ac.fetch_curation_state(["arr_deriv_c"])
    is_curated, ts = state["arr_deriv_c"]
    assert is_curated is True
    assert ts == curated_at.isoformat()


@pytest.mark.asyncio
async def test_fetch_curation_state_no_library_rows_is_null(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_nohar")
    # No pattern rows seeded.

    state = await ac.fetch_curation_state(["arr_deriv_nohar"])
    assert state == {"arr_deriv_nohar": (None, None)}


@pytest.mark.asyncio
async def test_fetch_curation_state_batch_is_single_query(neo4j_driver):
    """N arrangements → 1 Cypher statement (no N+1).

    Verified by patching driver.session().run and counting invocations.
    """
    from unittest.mock import patch, AsyncMock

    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    for i in range(5):
        arr_id = f"arr_batch_{i}"
        await _seed_arrangement(neo4j_driver, arr_id)
        await _seed_pattern(pl, arr_id)

    ids = [f"arr_batch_{i}" for i in range(5)]
    # Count session.run invocations during fetch_curation_state.
    from neo4j import AsyncSession
    original_run = AsyncSession.run
    call_count = 0
    async def counting_run(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_run(self, *args, **kwargs)
    with patch.object(AsyncSession, "run", counting_run):
        await ac.fetch_curation_state(ids)
    assert call_count == 1, f"expected 1 query, got {call_count}"


@pytest.mark.asyncio
async def test_fetch_curation_state_empty_list(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    state = await ac.fetch_curation_state([])
    assert state == {}
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/integration/test_arrangement_curation_derivation.py -v
```
Expected: FAIL — `fetch_curation_state` doesn't exist.

- [ ] **Step 3: Implement**

Replace `backend/src/explorator/graph/arrangement_candidate_repo.py`:

```python
"""Neo4j repository for ArrangementCandidate nodes."""
from typing import Any

from explorator.graph.repository import BaseRepository, _neo4j_deserialize


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"

    async def list_finalists_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Return arrangements for a session that carry a finalist role in metadata.

        `persist_realization` stamps `metadata.role` with one of
        ``"safest" | "best_loop" | "most_experimental"`` before persisting.
        Metadata is stored as a JSON string (see `_neo4j_safe`), so we match
        on the literal ``"role"`` substring and defer dict hydration to
        `_neo4j_deserialize`.
        """
        query = """
            MATCH (a:ArrangementCandidate {session_id: $session_id})
            WHERE a.metadata IS NOT NULL
              AND a.metadata CONTAINS '"role"'
            RETURN properties(a) AS props
            ORDER BY a.weighted_total DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            records = await result.data()
            return [_neo4j_deserialize(dict(r["props"])) for r in records]

    async def get_progression_candidate(self, pc_id: str) -> dict[str, Any] | None:
        """Fetch a progression candidate by id (used during harvest reconstruction)."""
        query = """
            MATCH (p:ProgressionCandidate {id: $id})
            RETURN properties(p) AS props
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=pc_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["props"]))

    async def fetch_curation_state(
        self, arrangement_ids: list[str]
    ) -> dict[str, tuple[bool | None, str | None]]:
        """Batch-fetch (is_curated, curated_at) for the given arrangements.

        Single-round-trip LEFT-JOIN derivation per M5d-3 spec. Returns a dict
        keyed by arrangement_id with `(is_curated, curated_at_iso)`. A tuple
        value of `(None, None)` means no non-deleted PatternLibraryEntry
        exists for the arrangement — treat as "not yet harvested." Since
        arrangement-level fan-out keeps facet rows in sync, any single row is
        the source of truth for the arrangement's curation state.
        """
        if not arrangement_ids:
            return {}
        query = """
        UNWIND $arrangement_ids AS aid
        MATCH (a:ArrangementCandidate {id: aid})
        OPTIONAL MATCH (p:PatternLibraryEntry)
          WHERE p.source_candidate_id = a.id AND p.deleted_at IS NULL
        WITH a, head(collect(p)) AS p
        RETURN a.id AS arrangement_id,
               p.is_curated AS is_curated,
               p.curated_at AS curated_at
        """
        async with self.driver.session() as session:
            result = await session.run(query, arrangement_ids=arrangement_ids)
            records = await result.data()
        return {
            r["arrangement_id"]: (r["is_curated"], r["curated_at"])
            for r in records
        }
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_arrangement_curation_derivation.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/arrangement_candidate_repo.py backend/tests/integration/test_arrangement_curation_derivation.py
git commit -m "feat(m5d-3): batch fetch_curation_state on ArrangementCandidateRepo"
```

---

## Part 4 — Curation service and API endpoint

### Task 8: Curation service (atomic event + fan-out)

**Files:**
- Create: `backend/src/explorator/services/pattern_library/curation_service.py`
- Test: `backend/tests/integration/test_curation_service.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/integration/test_curation_service.py`:

```python
import pytest
from datetime import timezone

from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.feedback_repo import FeedbackEventRepo
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.curation_service import (
    ArrangementNotFound,
    PatternsNotHarvested,
    curate_arrangement,
)


async def _seed(driver, arr_id, session_id="sess_curate"):
    async with driver.session() as s:
        await s.run(
            "MERGE (s:Session {id: $sid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) SET a.session_id = $sid",
            sid=session_id, aid=arr_id,
        )


@pytest.mark.asyncio
async def test_curate_arrangement_writes_event_and_flips_patterns(neo4j_driver):
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed(neo4j_driver, "arr_svc_ok")
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_svc_ok",
        success_metrics={"weighted_total": 0.7},
    ))

    result = await curate_arrangement(
        driver=neo4j_driver,
        arrangement_id="arr_svc_ok",
        is_curated=True,
    )

    assert result.is_curated is True
    assert result.curated_at is not None
    assert len(result.affected_pattern_ids) == 1

    # Event was written.
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    curation_events = [e for e in events if e.get("feedback_type") == "pattern_curation"]
    assert len(curation_events) == 1
    assert curation_events[0]["content"] == "curated"
    assert curation_events[0]["candidate_id"] == "arr_svc_ok"


@pytest.mark.asyncio
async def test_curate_arrangement_404_on_missing_arrangement(neo4j_driver):
    with pytest.raises(ArrangementNotFound):
        await curate_arrangement(
            driver=neo4j_driver,
            arrangement_id="arr_does_not_exist",
            is_curated=True,
        )


@pytest.mark.asyncio
async def test_curate_arrangement_409_when_no_patterns_and_no_event(neo4j_driver, caplog):
    import logging
    await _seed(neo4j_driver, "arr_svc_noharv")
    # No PatternLibraryEntry seeded.

    caplog.set_level(logging.WARNING)
    with pytest.raises(PatternsNotHarvested):
        await curate_arrangement(
            driver=neo4j_driver,
            arrangement_id="arr_svc_noharv",
            is_curated=True,
        )
    # No event should have been written.
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    curation_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_svc_noharv"
    ]
    assert curation_events == []
    # WARN log mentions the arrangement and session.
    assert any("arr_svc_noharv" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_curate_then_uncurate_two_events_final_state_uncurated(neo4j_driver):
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed(neo4j_driver, "arr_svc_flip")
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_svc_flip",
        success_metrics={"weighted_total": 0.7},
    ))

    await curate_arrangement(
        driver=neo4j_driver, arrangement_id="arr_svc_flip", is_curated=True,
    )
    result = await curate_arrangement(
        driver=neo4j_driver, arrangement_id="arr_svc_flip", is_curated=False,
    )
    assert result.is_curated is False
    assert result.curated_at is None
    fb_repo = FeedbackEventRepo(neo4j_driver)
    events = await fb_repo.list_by_session("sess_curate")
    flip_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_svc_flip"
    ]
    assert len(flip_events) == 2
    assert {e["content"] for e in flip_events} == {"curated", "uncurated"}
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/integration/test_curation_service.py -v
```
Expected: FAIL — service does not exist.

- [ ] **Step 3: Implement the service**

Create `backend/src/explorator/services/pattern_library/curation_service.py`:

```python
"""Orchestrates arrangement-level pattern curation (M5d-3).

Writes an append-only UserFeedbackEvent and updates the denormalized
is_curated/curated_at fields on every non-deleted PatternLibraryEntry row
for the arrangement — both inside a single Neo4j transaction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from neo4j import AsyncDriver

from explorator.graph.repository import _neo4j_safe
from explorator.models.memory import UserFeedbackEvent
from explorator.utils import utc_now

logger = logging.getLogger(__name__)


class ArrangementNotFound(Exception):
    """Raised when the arrangement_id doesn't exist. Maps to HTTP 404."""


class PatternsNotHarvested(Exception):
    """Raised when an arrangement exists but has no non-deleted library rows.

    Maps to HTTP 409. Frontend should prevent this via the disabled-star UX.
    """


@dataclass(frozen=True)
class CurationResult:
    arrangement_id: str
    is_curated: bool
    curated_at: datetime | None
    affected_pattern_ids: list[str]


async def curate_arrangement(
    *,
    driver: AsyncDriver,
    arrangement_id: str,
    is_curated: bool,
) -> CurationResult:
    """Toggle curation on an arrangement. Atomic: event + fan-out in one tx.

    Raises:
        ArrangementNotFound: no ArrangementCandidate with that id.
        PatternsNotHarvested: arrangement exists but no non-deleted
            PatternLibraryEntry rows match (no event is written).
    """
    now = utc_now()
    content = "curated" if is_curated else "uncurated"

    async with driver.session() as neo_session:
        # Step 1 — resolve arrangement + its session_id; also discover which
        # non-deleted pattern rows would be affected. This is a read-only
        # probe; no writes yet. We do it outside the transaction so we can
        # decide between 404 / 409 before starting one.
        result = await neo_session.run(
            "MATCH (a:ArrangementCandidate {id: $aid}) "
            "OPTIONAL MATCH (p:PatternLibraryEntry) "
            "  WHERE p.source_candidate_id = a.id AND p.deleted_at IS NULL "
            "RETURN a.session_id AS session_id, collect(p.id) AS pattern_ids",
            aid=arrangement_id,
        )
        record = await result.single()
        if record is None:
            raise ArrangementNotFound(arrangement_id)
        session_id = record["session_id"]
        pattern_ids = [pid for pid in record["pattern_ids"] if pid is not None]
        if not pattern_ids:
            logger.warning(
                "curation attempted with no harvested patterns "
                "(arrangement_id=%s session_id=%s)",
                arrangement_id, session_id,
            )
            raise PatternsNotHarvested(arrangement_id)

        # Step 2 — atomic write: event + fan-out + (Session)-[:HAS_FEEDBACK]->(event).
        event = UserFeedbackEvent(
            session_id=session_id,
            candidate_id=arrangement_id,
            feedback_type="pattern_curation",
            content=content,
        )
        event_props = _neo4j_safe(event.model_dump(mode="json"))

        tx = await neo_session.begin_transaction()
        try:
            await tx.run(
                "CREATE (e:UserFeedbackEvent $props) SET e.id = $props.id",
                props=event_props,
            )
            await tx.run(
                "MATCH (s:Session {id: $sid}), (e:UserFeedbackEvent {id: $eid}) "
                "CREATE (s)-[:HAS_FEEDBACK]->(e)",
                sid=session_id, eid=event.id,
            )
            await tx.run(
                "MATCH (e:UserFeedbackEvent {id: $eid}), (a {id: $aid}) "
                "CREATE (e)-[:ABOUT]->(a)",
                eid=event.id, aid=arrangement_id,
            )
            await tx.run(
                "MATCH (p:PatternLibraryEntry {source_candidate_id: $aid}) "
                "WHERE p.deleted_at IS NULL "
                "SET p.is_curated = $is_curated, "
                "    p.curated_at = CASE WHEN $is_curated THEN $now ELSE NULL END",
                aid=arrangement_id, is_curated=is_curated, now=now.isoformat(),
            )
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise

    return CurationResult(
        arrangement_id=arrangement_id,
        is_curated=is_curated,
        curated_at=now if is_curated else None,
        affected_pattern_ids=pattern_ids,
    )
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/integration/test_curation_service.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_library/curation_service.py backend/tests/integration/test_curation_service.py
git commit -m "feat(m5d-3): atomic curation service (event + fan-out in one tx)"
```

---

### Task 9: Extend `PatternItem` schema + projection

**Files:**
- Modify: `backend/src/explorator/api/schemas/patterns.py:8-22`
- Modify: `backend/src/explorator/api/routes/patterns.py:28-40` (projection fn)
- Test: `backend/tests/api/test_patterns_router.py` (append)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/api/test_patterns_router.py`:

```python
@pytest.mark.asyncio
async def test_list_patterns_response_includes_curation_fields(
    client, neo4j_driver
):
    """GET /v1/patterns response items carry is_curated + curated_at."""
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry

    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="cand_curation_schema",
        success_metrics={"weighted_total": 0.5},
    ))

    response = await client.get("/v1/patterns")
    assert response.status_code == 200
    items = response.json()["items"]
    match = next(i for i in items if i["source_candidate_id"] == "cand_curation_schema")
    assert match["is_curated"] is False
    assert match["curated_at"] is None
```

- [ ] **Step 2: Verify fail**

```bash
cd backend && uv run pytest tests/api/test_patterns_router.py::test_list_patterns_response_includes_curation_fields -v
```
Expected: FAIL — `is_curated` not in response.

- [ ] **Step 3: Extend schema**

In `backend/src/explorator/api/schemas/patterns.py`, edit `PatternItem` (lines 8-22):

```python
class PatternItem(BaseModel):
    """Public-facing projection of PatternLibraryEntry.

    Drops `embedding` (large, useless in browser) and `deleted_at` (404 masks it).
    """
    id: str
    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    created_at: datetime
    is_curated: bool = False
    curated_at: datetime | None = None
```

- [ ] **Step 4: Map fields in projection**

In `backend/src/explorator/api/routes/patterns.py:28-40`, edit `_to_pattern_item`:

```python
def _to_pattern_item(entry: dict) -> PatternItem:
    """Project a PatternLibraryEntry dict to the public PatternItem schema."""
    return PatternItem(
        id=entry["id"],
        pattern_type=entry["pattern_type"],
        genre=entry["genre"],
        tags=entry.get("tags") or [],
        source_candidate_id=entry["source_candidate_id"],
        abstracted_pattern=entry.get("abstracted_pattern") or {},
        success_metrics=entry.get("success_metrics") or {},
        notes=entry.get("notes") or "",
        created_at=entry["created_at"],
        is_curated=bool(entry.get("is_curated") or False),
        curated_at=entry.get("curated_at"),
    )
```

- [ ] **Step 5: Verify pass**

```bash
cd backend && uv run pytest tests/api/test_patterns_router.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/api/schemas/patterns.py backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d-3): expose is_curated/curated_at on PatternItem"
```

---

### Task 10: `GET /v1/patterns` accepts `curated_only`

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py:43-68`
- Test: `backend/tests/api/test_patterns_router.py` (append)

- [ ] **Step 1: Write failing test**

Append to `backend/tests/api/test_patterns_router.py`:

```python
@pytest.mark.asyncio
async def test_list_patterns_curated_only_filter(client, neo4j_driver):
    from datetime import datetime, timezone
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry

    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="cand_api_curated",
        success_metrics={"weighted_total": 0.5},
    ))
    await repo.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="cand_api_uncurated",
        success_metrics={"weighted_total": 0.4},
    ))
    await repo.toggle_curation(
        arrangement_id="cand_api_curated",
        is_curated=True,
        now=datetime(2026, 4, 24, 15, 0, tzinfo=timezone.utc),
    )

    response = await client.get("/v1/patterns?curated_only=true")
    assert response.status_code == 200
    ids = {i["source_candidate_id"] for i in response.json()["items"]}
    assert "cand_api_curated" in ids
    assert "cand_api_uncurated" not in ids
```

- [ ] **Step 2: Verify fail**

Expected: FAIL — param rejected or ignored.

- [ ] **Step 3: Thread query param**

In `backend/src/explorator/api/routes/patterns.py`, edit `list_patterns` signature + filter passthrough:

```python
@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    genre: str | None = Query(None),
    pattern_type: str | None = Query(None),
    curated_only: bool = Query(False),
    after_score: float | None = Query(None),
    after_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternListResponse:
    try:
        cursor = parse_cursor(after_score, after_id)
    except InvalidCursor as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    items, next_cursor = await repo.list_page(
        filters=PatternFilters(
            genre=genre, pattern_type=pattern_type, curated_only=curated_only,
        ),
        cursor=cursor,
        limit=limit,
    )
    return PatternListResponse(
        items=[_to_pattern_item(e) for e in items],
        next_cursor=(
            CursorResponse(after_score=next_cursor.after_score, after_id=next_cursor.after_id)
            if next_cursor else None
        ),
    )
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/api/test_patterns_router.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d-3): accept curated_only query param on GET /v1/patterns"
```

---

### Task 11: Enrich arrangement endpoints with curation state

**Files:**
- Modify: `backend/src/explorator/api/routes/realization_rounds.py:74-123`
- Test: `backend/tests/api/test_arrangements_curation.py` (new)

- [ ] **Step 1: Write failing test**

Create `backend/tests/api/test_arrangements_curation.py`:

```python
import pytest
from datetime import datetime, timezone

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


async def _seed_candidate_and_arrangement(driver, pc_id, arr_id, session_id="sess_arr"):
    async with driver.session() as s:
        await s.run(
            "MERGE (pc:ProgressionCandidate {id: $pcid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) "
            "SET a.progression_candidate_id = $pcid, a.session_id = $sid, "
            "    a.weighted_total = 0.7, a.rank_within_round = 1",
            pcid=pc_id, aid=arr_id, sid=session_id,
        )


@pytest.mark.asyncio
async def test_list_arrangements_is_curated_null_when_not_harvested(
    client, neo4j_driver
):
    """No PatternLibraryEntry rows → is_curated is null (not false)."""
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_null", "arr_null")
    response = await client.get("/v1/candidates/pc_null/arrangements")
    assert response.status_code == 200
    arr = next(a for a in response.json() if a["id"] == "arr_null")
    assert arr["is_curated"] is None
    assert arr["curated_at"] is None


@pytest.mark.asyncio
async def test_list_arrangements_is_curated_false_after_harvest(
    client, neo4j_driver
):
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_f", "arr_false")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_false",
        success_metrics={"weighted_total": 0.7},
    ))
    response = await client.get("/v1/candidates/pc_f/arrangements")
    arr = next(a for a in response.json() if a["id"] == "arr_false")
    assert arr["is_curated"] is False
    assert arr["curated_at"] is None


@pytest.mark.asyncio
async def test_get_arrangement_curated_true_after_toggle(
    client, neo4j_driver
):
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_t", "arr_true")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_true",
        success_metrics={"weighted_total": 0.7},
    ))
    ts = datetime(2026, 4, 24, 16, 0, tzinfo=timezone.utc)
    await pl.toggle_curation(arrangement_id="arr_true", is_curated=True, now=ts)

    response = await client.get("/v1/arrangements/arr_true")
    assert response.status_code == 200
    body = response.json()
    assert body["is_curated"] is True
    assert body["curated_at"] is not None
```

- [ ] **Step 2: Verify fail**

Expected: FAIL — `is_curated` key absent.

- [ ] **Step 3: Enrich both endpoints**

In `backend/src/explorator/api/routes/realization_rounds.py`, edit `list_arrangements` (lines 74-88) and `get_arrangement` (lines 91-123).

Add this import at the top:

```python
from explorator.graph.arrangement_candidate_repo import (
    ArrangementCandidateRepo as ArrangementCandidateGraphRepo,
)
```

Replace `list_arrangements`:

```python
@router.get("/candidates/{candidate_id}/arrangements")
async def list_arrangements(candidate_id: str, driver: AsyncDriver = Depends(get_neo4j_driver)) -> list[dict[str, Any]]:  # noqa: B008
    """List arrangement candidates for a progression candidate."""
    repo = ArrangementCandidateRepo(driver)
    results = await repo.query_by_property("progression_candidate_id", candidate_id)

    sc_repo = ScorecardRepo(driver)
    for r in results:
        scorecards = await sc_repo.query_by_property("candidate_id", r.get("id"))
        if scorecards:
            sc = scorecards[0]
            r["weighted_total"] = sc.get("weighted_total", 0.0)
            r["rank_within_round"] = sc.get("rank_within_round", 0)

    # Batch-derive curation state for all returned arrangements in one query.
    graph_repo = ArrangementCandidateGraphRepo(driver)
    curation = await graph_repo.fetch_curation_state([r["id"] for r in results if r.get("id")])
    for r in results:
        is_curated, curated_at = curation.get(r.get("id"), (None, None))
        r["is_curated"] = is_curated
        r["curated_at"] = curated_at

    return results
```

Replace `get_arrangement` (add derivation block after existing enrichment, before `return arrangement`):

```python
    sc_repo = ScorecardRepo(driver)
    scorecards = await sc_repo.query_by_property("candidate_id", arrangement_id)
    if scorecards:
        arrangement["scorecard"] = scorecards[0]

    # Curation state derivation (M5d-3). Nullable; see spec.
    graph_repo = ArrangementCandidateGraphRepo(driver)
    curation = await graph_repo.fetch_curation_state([arrangement_id])
    is_curated, curated_at = curation.get(arrangement_id, (None, None))
    arrangement["is_curated"] = is_curated
    arrangement["curated_at"] = curated_at

    return arrangement
```

- [ ] **Step 4: Verify pass**

```bash
cd backend && uv run pytest tests/api/test_arrangements_curation.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/realization_rounds.py backend/tests/api/test_arrangements_curation.py
git commit -m "feat(m5d-3): derive is_curated/curated_at on arrangement responses"
```

---

### Task 12: `POST /v1/arrangements/{id}/curation` endpoint

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py` (add endpoint)
- Modify: `backend/src/explorator/api/schemas/patterns.py` (add request/response)
- Test: `backend/tests/api/test_curation_router.py` (new)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/api/test_curation_router.py`:

```python
import pytest


async def _seed(driver, arr_id, session_id="sess_curation_api"):
    async with driver.session() as s:
        await s.run(
            "MERGE (s:Session {id: $sid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) SET a.session_id = $sid",
            sid=session_id, aid=arr_id,
        )


@pytest.mark.asyncio
async def test_post_curation_curate_happy_path(client, neo4j_driver):
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry
    await _seed(neo4j_driver, "arr_api_curate")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_api_curate",
        success_metrics={"weighted_total": 0.7},
    ))

    response = await client.post(
        "/v1/arrangements/arr_api_curate/curation",
        json={"curated": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["arrangement_id"] == "arr_api_curate"
    assert body["is_curated"] is True
    assert body["curated_at"] is not None
    assert len(body["affected_pattern_ids"]) == 1


@pytest.mark.asyncio
async def test_post_curation_uncurate(client, neo4j_driver):
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.models.memory import PatternLibraryEntry
    from explorator.utils import utc_now
    await _seed(neo4j_driver, "arr_api_uncurate")
    pl = PatternLibraryRepo(neo4j_driver)
    await pl.upsert(PatternLibraryEntry(
        pattern_type="progression", genre="jazz",
        source_candidate_id="arr_api_uncurate",
        success_metrics={"weighted_total": 0.7},
    ))
    await pl.toggle_curation(
        arrangement_id="arr_api_uncurate", is_curated=True, now=utc_now(),
    )

    response = await client.post(
        "/v1/arrangements/arr_api_uncurate/curation",
        json={"curated": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_curated"] is False
    assert body["curated_at"] is None


@pytest.mark.asyncio
async def test_post_curation_404_unknown_arrangement(client):
    response = await client.post(
        "/v1/arrangements/arr_does_not_exist/curation",
        json={"curated": True},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_curation_409_no_harvested_patterns(client, neo4j_driver):
    await _seed(neo4j_driver, "arr_api_noharv")
    # No PatternLibraryEntry seeded.

    response = await client.post(
        "/v1/arrangements/arr_api_noharv/curation",
        json={"curated": True},
    )
    assert response.status_code == 409

    # Confirm no event was written.
    from explorator.graph.feedback_repo import FeedbackEventRepo
    fb = FeedbackEventRepo(neo4j_driver)
    events = await fb.list_by_session("sess_curation_api")
    curation_events = [
        e for e in events
        if e.get("feedback_type") == "pattern_curation"
        and e.get("candidate_id") == "arr_api_noharv"
    ]
    assert curation_events == []


@pytest.mark.asyncio
async def test_post_curation_422_missing_body(client, neo4j_driver):
    await _seed(neo4j_driver, "arr_api_badbody")
    response = await client.post(
        "/v1/arrangements/arr_api_badbody/curation",
        json={},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Verify fail**

Expected: FAIL — endpoint 404 (does not exist).

- [ ] **Step 3: Add request/response schemas**

Append to `backend/src/explorator/api/schemas/patterns.py`:

```python
class CurationRequest(BaseModel):
    curated: bool


class CurationResponse(BaseModel):
    arrangement_id: str
    is_curated: bool
    curated_at: datetime | None = None
    affected_pattern_ids: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add the endpoint**

Append to `backend/src/explorator/api/routes/patterns.py`:

```python
from explorator.api.schemas.patterns import CurationRequest, CurationResponse
from explorator.services.pattern_library.curation_service import (
    ArrangementNotFound,
    PatternsNotHarvested,
    curate_arrangement,
)
from explorator.api.deps import get_neo4j_driver
from neo4j import AsyncDriver


@router.post(
    "/arrangements/{arrangement_id}/curation",
    response_model=CurationResponse,
)
async def post_curation(
    arrangement_id: str,
    request: CurationRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> CurationResponse:
    try:
        result = await curate_arrangement(
            driver=driver,
            arrangement_id=arrangement_id,
            is_curated=request.curated,
        )
    except ArrangementNotFound as exc:
        raise HTTPException(status_code=404, detail="arrangement not found") from exc
    except PatternsNotHarvested as exc:
        raise HTTPException(
            status_code=409,
            detail="arrangement not yet harvested",
        ) from exc
    return CurationResponse(
        arrangement_id=result.arrangement_id,
        is_curated=result.is_curated,
        curated_at=result.curated_at,
        affected_pattern_ids=result.affected_pattern_ids,
    )
```

- [ ] **Step 5: Verify pass**

```bash
cd backend && uv run pytest tests/api/test_curation_router.py -v
```
Expected: all pass.

- [ ] **Step 6: Run full backend suite**

```bash
cd backend && make test
```
Expected: all pre-existing green tests remain green.

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/src/explorator/api/schemas/patterns.py backend/tests/api/test_curation_router.py
git commit -m "feat(m5d-3): POST /v1/arrangements/{id}/curation endpoint"
```

---

## Part 5 — Frontend types & API client

### Task 13: TypeScript type updates

**Files:**
- Modify: `frontend/src/api/types.ts:25-50`
- Modify: `frontend/src/services/api.ts:128-137`

- [ ] **Step 1: Update `PatternItem` and `PatternFilters` types**

In `frontend/src/api/types.ts`:

```typescript
export interface PatternItem {
  id: string;
  pattern_type: string;
  genre: string;
  tags: string[];
  source_candidate_id: string;
  abstracted_pattern: Record<string, unknown>;
  success_metrics: Record<string, number>;
  notes: string;
  created_at: string;
  is_curated: boolean;
  curated_at: string | null;
}

export interface PatternCursor {
  after_score: number;
  after_id: string;
}

export interface PatternListResponse {
  items: PatternItem[];
  next_cursor: PatternCursor | null;
}

export interface PatternFilters {
  genre?: string;
  pattern_type?: string;
  curated_only?: boolean;
}
```

- [ ] **Step 2: Update `ArrangementSummary` type**

In `frontend/src/services/api.ts`, find the `ArrangementSummary` interface (around line 128) and add:

```typescript
export interface ArrangementSummary {
  id: string
  status: "draft" | "selected" | "rejected"
  progression_candidate_id: string
  voicing_plan_id: string
  bass_line_id: string
  weighted_total: number
  rank_within_round: number
  rationale: string
  // M5d-3: null = arrangement not yet harvested into library;
  //        false/true = explicit user curation state.
  is_curated?: boolean | null
  curated_at?: string | null
}
```

- [ ] **Step 3: tsc check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors (new fields are optional).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/services/api.ts
git commit -m "feat(m5d-3): mirror curation fields on frontend types"
```

---

### Task 14: `toggleCuration` API client + `curated_only` threading

**Files:**
- Modify: `frontend/src/api/patterns.ts`
- Test: `frontend/src/api/__tests__/patterns.test.ts` (new or append)

- [ ] **Step 1: Write failing test**

Create (or append to) `frontend/src/api/__tests__/patterns.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listPatterns, toggleCuration } from '../patterns';

const origFetch = global.fetch;

beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  global.fetch = origFetch;
});

describe('patterns API', () => {
  it('listPatterns threads curated_only into querystring', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    });
    await listPatterns({ curated_only: true });
    const url = (global.fetch as any).mock.calls[0][0];
    expect(url).toMatch(/curated_only=true/);
  });

  it('listPatterns omits curated_only when false/undefined', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    });
    await listPatterns({});
    const url = (global.fetch as any).mock.calls[0][0];
    expect(url).not.toMatch(/curated_only/);
  });

  it('toggleCuration POSTs to the right URL with curated boolean', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        arrangement_id: 'arr_x',
        is_curated: true,
        curated_at: '2026-04-24T12:00:00Z',
        affected_pattern_ids: ['pat_1', 'pat_2'],
      }),
    });
    const result = await toggleCuration('arr_x', true);
    const [url, init] = (global.fetch as any).mock.calls[0];
    expect(url).toMatch(/\/v1\/arrangements\/arr_x\/curation$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ curated: true });
    expect(result.is_curated).toBe(true);
    expect(result.affected_pattern_ids).toEqual(['pat_1', 'pat_2']);
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- patterns.test
```
Expected: FAIL — `toggleCuration` not exported; `curated_only` not in query.

- [ ] **Step 3: Update `frontend/src/api/patterns.ts`**

Read the current file first, then update. The new shape (keeping existing functions intact):

```typescript
// In listPatterns (existing), build URL param list and append:
if (filters.curated_only) {
  params.set('curated_only', 'true');
}
```

and add a new export:

```typescript
export async function toggleCuration(
  arrangementId: string,
  curated: boolean,
): Promise<{
  arrangement_id: string;
  is_curated: boolean;
  curated_at: string | null;
  affected_pattern_ids: string[];
}> {
  const res = await fetch(`/v1/arrangements/${arrangementId}/curation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curated }),
  });
  if (!res.ok) {
    throw new Error(`toggleCuration ${res.status}: ${await res.text()}`);
  }
  return res.json();
}
```

(If the existing `listPatterns` builds URLs in a different style, keep that style and just add the `curated_only` branch in the matching idiom.)

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- patterns.test
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/patterns.ts frontend/src/api/__tests__/patterns.test.ts
git commit -m "feat(m5d-3): toggleCuration API client + curated_only query threading"
```

---

## Part 6 — Frontend stores

### Task 15: `patternFiltersStore.setCuratedOnly`

**Files:**
- Modify: `frontend/src/stores/patternFiltersStore.ts`
- Test: `frontend/src/stores/__tests__/patternFiltersStore.test.ts` (new)

- [ ] **Step 1: Write failing test**

Create `frontend/src/stores/__tests__/patternFiltersStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { usePatternFiltersStore } from '../patternFiltersStore';

describe('patternFiltersStore', () => {
  beforeEach(() => {
    usePatternFiltersStore.setState({ filters: {} });
  });

  it('setCuratedOnly(true) sets curated_only filter', () => {
    usePatternFiltersStore.getState().setCuratedOnly(true);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBe(true);
  });

  it('setCuratedOnly(false) clears curated_only from filters', () => {
    usePatternFiltersStore.setState({ filters: { curated_only: true } });
    usePatternFiltersStore.getState().setCuratedOnly(false);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBeUndefined();
  });

  it('setCuratedOnly does not disturb other filters', () => {
    usePatternFiltersStore.setState({ filters: { genre: 'jazz', pattern_type: 'progression' } });
    usePatternFiltersStore.getState().setCuratedOnly(true);
    const { filters } = usePatternFiltersStore.getState();
    expect(filters.genre).toBe('jazz');
    expect(filters.pattern_type).toBe('progression');
    expect(filters.curated_only).toBe(true);
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- patternFiltersStore
```
Expected: FAIL — `setCuratedOnly` not on store.

- [ ] **Step 3: Update the store**

Replace `frontend/src/stores/patternFiltersStore.ts`:

```typescript
import { create } from 'zustand';
import type { PatternFilters } from '../api/types';

interface PatternFiltersState {
  filters: PatternFilters;
  setFilter: (patch: PatternFilters) => void;
  setCuratedOnly: (value: boolean) => void;
}

export const usePatternFiltersStore = create<PatternFiltersState>((set) => ({
  filters: {},
  setFilter: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
  setCuratedOnly: (value) =>
    set((state) => {
      const next = { ...state.filters };
      if (value) {
        next.curated_only = true;
      } else {
        delete next.curated_only;
      }
      return { filters: next };
    }),
}));
```

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- patternFiltersStore
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/patternFiltersStore.ts frontend/src/stores/__tests__/patternFiltersStore.test.ts
git commit -m "feat(m5d-3): setCuratedOnly action on patternFiltersStore"
```

---

### Task 16: `patternLibraryStore.toggleCuration`

**Files:**
- Modify: `frontend/src/stores/patternLibraryStore.ts`
- Test: `frontend/src/stores/__tests__/patternLibraryStore.test.ts` (append)

Semantics: flip `is_curated` on **every item whose `source_candidate_id` matches** (fan-out mirrors the backend). Optimistic, reconcile on success, revert on failure, toast on both.

- [ ] **Step 1: Write failing test**

Append to `frontend/src/stores/__tests__/patternLibraryStore.test.ts`:

```typescript
import * as api from '../../api/patterns';
import { toast } from '../../lib/toast';

vi.mock('../../lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

describe('patternLibraryStore.toggleCuration', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
  });

  it('fans out is_curated across all items with matching source_candidate_id', async () => {
    usePatternLibraryStore.setState({
      items: [
        { id: 'p1', source_candidate_id: 'arr_x', is_curated: false, curated_at: null } as any,
        { id: 'p2', source_candidate_id: 'arr_x', is_curated: false, curated_at: null } as any,
        { id: 'p3', source_candidate_id: 'arr_y', is_curated: false, curated_at: null } as any,
      ],
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x',
      is_curated: true,
      curated_at: '2026-04-24T12:00:00Z',
      affected_pattern_ids: ['p1', 'p2'],
    });

    await usePatternLibraryStore.getState().toggleCuration('arr_x', true);

    const items = usePatternLibraryStore.getState().items;
    expect(items.find((i) => i.id === 'p1')!.is_curated).toBe(true);
    expect(items.find((i) => i.id === 'p2')!.is_curated).toBe(true);
    expect(items.find((i) => i.id === 'p3')!.is_curated).toBe(false);
    expect(toast.success).toHaveBeenCalledWith('Curated');
  });

  it('reverts optimistic flip + error-toasts on API failure', async () => {
    usePatternLibraryStore.setState({
      items: [
        { id: 'p1', source_candidate_id: 'arr_x', is_curated: false, curated_at: null } as any,
      ],
    });
    vi.spyOn(api, 'toggleCuration').mockRejectedValue(new Error('nope'));
    await expect(
      usePatternLibraryStore.getState().toggleCuration('arr_x', true),
    ).rejects.toThrow();

    expect(usePatternLibraryStore.getState().items[0].is_curated).toBe(false);
    expect(toast.error).toHaveBeenCalledWith('Failed to update curation');
  });

  it('toasts "Removed from curated" when flipping to false', async () => {
    usePatternLibraryStore.setState({
      items: [{ id: 'p1', source_candidate_id: 'arr_x', is_curated: true, curated_at: 'x' } as any],
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x', is_curated: false, curated_at: null,
      affected_pattern_ids: ['p1'],
    });

    await usePatternLibraryStore.getState().toggleCuration('arr_x', false);
    expect(toast.success).toHaveBeenCalledWith('Removed from curated');
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- patternLibraryStore
```
Expected: FAIL — `toggleCuration` not on store.

- [ ] **Step 3: Update the store**

Edit `frontend/src/stores/patternLibraryStore.ts`. Add to imports:

```typescript
import { toggleCuration as apiToggleCuration } from '../api/patterns';
import { toast } from '../lib/toast';
```

Add `toggleCuration` to the state interface and initial object. Full new shape:

```typescript
interface PatternLibraryState {
  items: PatternItem[];
  cursor: PatternCursor | null;
  hasMore: boolean;
  loading: boolean;
  error: string | null;

  loadMore: (filters: PatternFilters) => Promise<void>;
  removePattern: (id: string) => Promise<void>;
  toggleCuration: (arrangementId: string, nextState: boolean) => Promise<void>;
  reset: () => void;
}
```

Add the action inside the `create()` body:

```typescript
  toggleCuration: async (arrangementId, nextState) => {
    const prevItems = get().items;
    // Optimistic fan-out: flip every item with matching source_candidate_id.
    set({
      items: prevItems.map((p) =>
        p.source_candidate_id === arrangementId
          ? { ...p, is_curated: nextState, curated_at: nextState ? new Date().toISOString() : null }
          : p,
      ),
    });
    try {
      const resp = await apiToggleCuration(arrangementId, nextState);
      // Reconcile timestamps from the server (optional but cheap).
      set((state) => ({
        items: state.items.map((p) =>
          resp.affected_pattern_ids.includes(p.id)
            ? { ...p, is_curated: resp.is_curated, curated_at: resp.curated_at }
            : p,
        ),
      }));
      toast.success(nextState ? 'Curated' : 'Removed from curated');
    } catch (err) {
      set({ items: prevItems });
      toast.error('Failed to update curation');
      throw err;
    }
  },
```

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- patternLibraryStore
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/patternLibraryStore.ts frontend/src/stores/__tests__/patternLibraryStore.test.ts
git commit -m "feat(m5d-3): toggleCuration action on patternLibraryStore"
```

---

### Task 17: `arrangementStore.toggleCuration`

**Files:**
- Modify: `frontend/src/stores/arrangementStore.ts`
- Test: `frontend/src/stores/__tests__/arrangementStore.test.ts` (new)

- [ ] **Step 1: Write failing test**

Create `frontend/src/stores/__tests__/arrangementStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useArrangementStore } from '../arrangementStore';
import * as api from '../../api/patterns';
import { toast } from '../../lib/toast';

vi.mock('../../lib/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

describe('arrangementStore.toggleCuration', () => {
  beforeEach(() => {
    useArrangementStore.getState().reset();
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('optimistically flips is_curated on the matching arrangement', async () => {
    useArrangementStore.setState({
      arrangements: [
        { id: 'arr_x', is_curated: false, curated_at: null } as any,
        { id: 'arr_y', is_curated: false, curated_at: null } as any,
      ],
    });
    vi.spyOn(api, 'toggleCuration').mockResolvedValue({
      arrangement_id: 'arr_x', is_curated: true,
      curated_at: '2026-04-24T12:00:00Z',
      affected_pattern_ids: ['p1'],
    });

    await useArrangementStore.getState().toggleCuration('arr_x', true);

    const { arrangements } = useArrangementStore.getState();
    expect(arrangements.find((a) => a.id === 'arr_x')!.is_curated).toBe(true);
    expect(arrangements.find((a) => a.id === 'arr_y')!.is_curated).toBe(false);
  });

  it('reverts + error-toasts on API failure', async () => {
    useArrangementStore.setState({
      arrangements: [{ id: 'arr_x', is_curated: false, curated_at: null } as any],
    });
    vi.spyOn(api, 'toggleCuration').mockRejectedValue(new Error('bad'));

    await expect(
      useArrangementStore.getState().toggleCuration('arr_x', true),
    ).rejects.toThrow();

    expect(useArrangementStore.getState().arrangements[0].is_curated).toBe(false);
    expect(toast.error).toHaveBeenCalledWith('Failed to update curation');
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- arrangementStore
```
Expected: FAIL — no `toggleCuration` method.

- [ ] **Step 3: Update the store**

Replace `frontend/src/stores/arrangementStore.ts`:

```typescript
import { create } from "zustand"
import type { ArrangementDetail, ArrangementSummary } from "../services/api"
import { toggleCuration as apiToggleCuration } from "../api/patterns"
import { toast } from "../lib/toast"

interface ArrangementState {
  arrangements: ArrangementSummary[]
  selectedArrangementId: string | null
  selectedDetail: ArrangementDetail | null
  loading: boolean
  error: string | null
  setArrangements: (arrangements: ArrangementSummary[]) => void
  setSelectedArrangementId: (id: string | null) => void
  setSelectedDetail: (detail: ArrangementDetail | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  toggleCuration: (arrangementId: string, nextState: boolean) => Promise<void>
  reset: () => void
}

export const useArrangementStore = create<ArrangementState>((set, get) => ({
  arrangements: [],
  selectedArrangementId: null,
  selectedDetail: null,
  loading: false,
  error: null,
  setArrangements: (arrangements) => set({ arrangements }),
  setSelectedArrangementId: (id) => set({ selectedArrangementId: id }),
  setSelectedDetail: (detail) => set({ selectedDetail: detail }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  toggleCuration: async (arrangementId, nextState) => {
    const prev = get().arrangements
    set({
      arrangements: prev.map((a) =>
        a.id === arrangementId
          ? { ...a, is_curated: nextState, curated_at: nextState ? new Date().toISOString() : null }
          : a,
      ),
    })
    try {
      const resp = await apiToggleCuration(arrangementId, nextState)
      set((state) => ({
        arrangements: state.arrangements.map((a) =>
          a.id === arrangementId
            ? { ...a, is_curated: resp.is_curated, curated_at: resp.curated_at }
            : a,
        ),
      }))
      toast.success(nextState ? "Curated" : "Removed from curated")
    } catch (err) {
      set({ arrangements: prev })
      toast.error("Failed to update curation")
      throw err
    }
  },
  reset: () => set({ arrangements: [], selectedArrangementId: null, selectedDetail: null, loading: false, error: null }),
}))
```

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- arrangementStore
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/arrangementStore.ts frontend/src/stores/__tests__/arrangementStore.test.ts
git commit -m "feat(m5d-3): toggleCuration action on arrangementStore"
```

---

## Part 7 — Frontend components

### Task 18: Shared `StarButton` component

Used by both `PatternCard` (non-null state) and `FinalistPanel` (nullable state). Three visual states per spec.

**Files:**
- Create: `frontend/src/components/StarButton.tsx`
- Test: `frontend/src/components/__tests__/StarButton.test.tsx`

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/__tests__/StarButton.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StarButton } from '../StarButton';

describe('StarButton', () => {
  it('renders outlined star when uncurated', () => {
    render(<StarButton isCurated={false} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    expect(btn).toHaveAttribute('aria-label', 'Mark as curated');
    expect(btn).not.toHaveAttribute('aria-disabled', 'true');
  });

  it('renders filled star when curated', () => {
    render(<StarButton isCurated={true} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(btn).toHaveAttribute('aria-label', 'Remove from curated');
  });

  it('renders disabled star when isCurated is null', () => {
    render(<StarButton isCurated={null} onToggle={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-disabled', 'true');
    expect(btn).toHaveAttribute('title', 'Available after the round completes');
  });

  it('calls onToggle with inverted state on click', () => {
    const onToggle = vi.fn();
    render(<StarButton isCurated={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it('does not call onToggle when disabled', () => {
    const onToggle = vi.fn();
    render(<StarButton isCurated={null} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- StarButton
```
Expected: FAIL — component doesn't exist.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/StarButton.tsx`:

```typescript
interface Props {
  isCurated: boolean | null;
  onToggle: (nextState: boolean) => void;
}

export function StarButton({ isCurated, onToggle }: Props) {
  const disabled = isCurated === null;
  const label = isCurated ? 'Remove from curated' : 'Mark as curated';
  const filled = isCurated === true;

  const handleClick = () => {
    if (disabled) return;
    onToggle(!isCurated);
  };

  return (
    <button
      onClick={handleClick}
      aria-label={label}
      aria-pressed={isCurated === true}
      aria-disabled={disabled || undefined}
      title={disabled ? 'Available after the round completes' : label}
      className="p-1 rounded transition-opacity"
      style={{
        color: 'var(--accent-primary)',
        background: 'transparent',
        opacity: disabled ? 0.35 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      <svg
        width="16" height="16" viewBox="0 0 24 24"
        fill={filled ? 'currentColor' : 'none'}
        stroke={filled ? 'none' : 'currentColor'}
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
    </button>
  );
}
```

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- StarButton
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StarButton.tsx frontend/src/components/__tests__/StarButton.test.tsx
git commit -m "feat(m5d-3): shared StarButton component (3 states)"
```

---

### Task 19: Integrate `StarButton` into `PatternCard`

**Files:**
- Modify: `frontend/src/components/patterns/PatternCard.tsx`
- Test: `frontend/src/components/patterns/__tests__/PatternCard.test.tsx` (append)

- [ ] **Step 1: Write failing test**

Append to `frontend/src/components/patterns/__tests__/PatternCard.test.tsx`:

```typescript
import { usePatternLibraryStore } from '../../../stores/patternLibraryStore';

describe('PatternCard curation', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
  });

  it('renders filled star when pattern.is_curated is true', () => {
    const curated: PatternItem = { ...item, is_curated: true, curated_at: '2026-04-24T12:00:00Z' };
    render(<PatternCard pattern={curated} onDelete={vi.fn()} />);
    expect(screen.getByLabelText('Remove from curated')).toBeInTheDocument();
  });

  it('renders outlined star when pattern.is_curated is false', () => {
    const uncurated: PatternItem = { ...item, is_curated: false, curated_at: null };
    render(<PatternCard pattern={uncurated} onDelete={vi.fn()} />);
    expect(screen.getByLabelText('Mark as curated')).toBeInTheDocument();
  });

  it('clicking star calls patternLibraryStore.toggleCuration with arrangement id', () => {
    const spy = vi.spyOn(usePatternLibraryStore.getState(), 'toggleCuration')
      .mockResolvedValue();
    const p: PatternItem = { ...item, is_curated: false, curated_at: null };
    render(<PatternCard pattern={p} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Mark as curated'));
    expect(spy).toHaveBeenCalledWith(item.source_candidate_id, true);
  });
});
```

Also update the existing fixture `item` at the top of the file to include the two new required fields:

```typescript
const item: PatternItem = {
  id: 'pat_0001',
  pattern_type: 'progression',
  genre: 'jazz',
  tags: ['role:safest', 'cadence:authentic'],
  source_candidate_id: 'cand_0001_xyz',
  abstracted_pattern: { foo: 'bar' },
  success_metrics: { weighted_total: 0.87 },
  notes: 'ii-V-I with tritone sub',
  created_at: '2026-04-19T00:00:00Z',
  is_curated: false,
  curated_at: null,
};
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- PatternCard
```
Expected: FAIL — star not rendered.

- [ ] **Step 3: Integrate `StarButton` into `PatternCard`**

Edit `frontend/src/components/patterns/PatternCard.tsx`:

```typescript
import type { PatternItem } from '../../api/types';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { StarButton } from '../StarButton';

interface Props {
  pattern: PatternItem;
  onDelete: (id: string) => void;
}

function shortHash(id: string): string {
  return id.length > 8 ? id.slice(-8) : id;
}

export function PatternCard({ pattern, onDelete }: Props) {
  const score = pattern.success_metrics.weighted_total ?? 0;
  const toggleCuration = usePatternLibraryStore((s) => s.toggleCuration);
  const handleDelete = () => {
    if (confirm('Delete this pattern? This cannot be undone.')) {
      onDelete(pattern.id);
    }
  };

  return (
    <div
      data-testid={`pattern-card-${pattern.id}`}
      className="rounded-md p-3 border"
      style={{
        background: 'var(--surface-2)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
          >
            {pattern.pattern_type}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {pattern.genre}
          </span>
          <span className="text-sm font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {score.toFixed(2)}
          </span>
          <span
            className="text-xs font-mono"
            style={{ color: 'var(--text-muted)' }}
            title={pattern.source_candidate_id}
          >
            src: {shortHash(pattern.source_candidate_id)}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <StarButton
            isCurated={pattern.is_curated}
            onToggle={(next) => {
              void toggleCuration(pattern.source_candidate_id, next).catch(() => {
                // Store already toasts on failure; swallow.
              });
            }}
          />
          <button
            onClick={handleDelete}
            aria-label={`Delete ${pattern.id}`}
            className="text-xs px-2 py-1 rounded transition-colors"
            style={{ color: 'var(--text-muted)', background: 'transparent' }}
            onMouseOver={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            Delete
          </button>
        </div>
      </div>
      {pattern.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {pattern.tags.map((t) => (
            <span
              key={t}
              className="text-xs px-1.5 py-0.5 rounded"
              style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <details>
        <summary className="text-xs cursor-pointer" style={{ color: 'var(--text-muted)' }}>
          abstracted_pattern
        </summary>
        <pre
          className="text-xs mt-1 p-2 rounded overflow-x-auto"
          style={{ background: 'var(--surface-1)', color: 'var(--text-muted)' }}
        >
          {JSON.stringify(pattern.abstracted_pattern, null, 2)}
        </pre>
      </details>
      {pattern.notes && (
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          {pattern.notes}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- PatternCard
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/patterns/PatternCard.tsx frontend/src/components/patterns/__tests__/PatternCard.test.tsx
git commit -m "feat(m5d-3): star button on PatternCard"
```

---

### Task 20: `Curated only` checkbox in `PatternFilters`

**Files:**
- Modify: `frontend/src/components/patterns/PatternFilters.tsx`
- Test: `frontend/src/components/patterns/__tests__/PatternFilters.test.tsx` (append or new)

- [ ] **Step 1: Read the current component first**

```bash
cat frontend/src/components/patterns/PatternFilters.tsx
```
(to preserve existing structure)

- [ ] **Step 2: Write failing test**

Create or append to `frontend/src/components/patterns/__tests__/PatternFilters.test.tsx`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PatternFilters } from '../PatternFilters';
import { usePatternFiltersStore } from '../../../stores/patternFiltersStore';

describe('PatternFilters curated-only', () => {
  beforeEach(() => {
    usePatternFiltersStore.setState({ filters: {} });
  });

  it('renders a Curated only checkbox, unchecked by default', () => {
    render(<PatternFilters />);
    const cb = screen.getByLabelText('Curated only') as HTMLInputElement;
    expect(cb).toBeInTheDocument();
    expect(cb.checked).toBe(false);
  });

  it('toggling the checkbox calls setCuratedOnly', () => {
    render(<PatternFilters />);
    const cb = screen.getByLabelText('Curated only') as HTMLInputElement;
    fireEvent.click(cb);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBe(true);
    fireEvent.click(cb);
    expect(usePatternFiltersStore.getState().filters.curated_only).toBeUndefined();
  });
});
```

- [ ] **Step 3: Verify fail**

```bash
cd frontend && npm test -- PatternFilters
```
Expected: FAIL — checkbox not rendered.

- [ ] **Step 4: Add the checkbox**

Append inside the filter row in `frontend/src/components/patterns/PatternFilters.tsx` (after the existing genre/type inputs, before the closing `</div>`):

```typescript
      <label
        className="flex items-center gap-2 text-sm cursor-pointer"
        style={{ color: 'var(--text-muted)' }}
      >
        <input
          type="checkbox"
          checked={filters.curated_only ?? false}
          onChange={(e) => setCuratedOnly(e.target.checked)}
        />
        Curated only
      </label>
```

And pull `setCuratedOnly` from the store alongside the existing imports at the top of the component:

```typescript
  const setCuratedOnly = usePatternFiltersStore((s) => s.setCuratedOnly);
```

- [ ] **Step 5: Verify pass**

```bash
cd frontend && npm test -- PatternFilters
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/patterns/PatternFilters.tsx frontend/src/components/patterns/__tests__/PatternFilters.test.tsx
git commit -m "feat(m5d-3): Curated only checkbox in PatternFilters"
```

---

### Task 21: `FinalistPanel` — remove Save button, add stars

**Files:**
- Modify: `frontend/src/components/FinalistPanel.tsx`
- Test: `frontend/src/components/__tests__/FinalistPanel.test.tsx` (append or new)

- [ ] **Step 1: Write failing tests**

Create or append to `frontend/src/components/__tests__/FinalistPanel.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FinalistPanel from '../FinalistPanel';
import { useArrangementStore } from '../../stores/arrangementStore';

const finalSelection = {
  selected_candidate_ids: ['arr_1', 'arr_2'],
  selection_roles: { arr_1: 'safest', arr_2: 'best_loop' },
} as any;

const arrangements = [
  { id: 'arr_1', weighted_total: 8.5, rationale: 'Safe', is_curated: false, curated_at: null } as any,
  { id: 'arr_2', weighted_total: 7.2, rationale: 'Loopy', is_curated: true, curated_at: '2026-04-24T12:00:00Z' } as any,
];

describe('FinalistPanel curation', () => {
  beforeEach(() => {
    useArrangementStore.getState().reset();
  });

  it('no longer renders the "Save to library" button', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    expect(screen.queryByTestId('save-finalists-to-library')).toBeNull();
  });

  it('renders stars per finalist matching their is_curated state', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    expect(screen.getByLabelText('Mark as curated')).toBeInTheDocument();
    expect(screen.getByLabelText('Remove from curated')).toBeInTheDocument();
  });

  it('renders disabled star when arrangement.is_curated is null (not yet harvested)', () => {
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={[
          { id: 'arr_1', weighted_total: 8.5, rationale: 'x', is_curated: null, curated_at: null } as any,
          { id: 'arr_2', weighted_total: 7.2, rationale: 'y', is_curated: null, curated_at: null } as any,
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_1"
      />,
    );
    const stars = screen.getAllByRole('button', { name: 'Mark as curated' });
    stars.forEach((s) => expect(s).toHaveAttribute('aria-disabled', 'true'));
  });

  it('clicking star calls arrangementStore.toggleCuration and does not select the card', () => {
    const spy = vi.spyOn(useArrangementStore.getState(), 'toggleCuration').mockResolvedValue();
    const onSelect = vi.fn();
    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={onSelect}
        sessionId="sess_1"
      />,
    );
    fireEvent.click(screen.getByLabelText('Mark as curated'));
    expect(spy).toHaveBeenCalledWith('arr_1', true);
    expect(onSelect).not.toHaveBeenCalled(); // click event should not bubble to card
  });
});
```

- [ ] **Step 2: Verify fail**

```bash
cd frontend && npm test -- FinalistPanel
```
Expected: FAIL — stars not rendered; Save button still present.

- [ ] **Step 3: Rewrite the component**

Replace `frontend/src/components/FinalistPanel.tsx`:

```typescript
import type { ArrangementSummary, FinalSelection } from '../services/api';
import { useArrangementStore } from '../stores/arrangementStore';
import { StarButton } from './StarButton';

interface FinalistPanelProps {
  finalSelection: FinalSelection;
  arrangements: ArrangementSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sessionId: string;
}

const ROLE_CONFIG: Record<string, { label: string; accent: string }> = {
  safest: { label: 'Safest', accent: 'var(--role-safest)' },
  best_loop: { label: 'Best Loop', accent: 'var(--role-loop)' },
  most_experimental: { label: 'Most Experimental', accent: 'var(--role-experimental)' },
};

function scoreColor(score: number): string {
  if (score >= 8) return 'var(--score-high)';
  if (score >= 6) return 'var(--score-mid)';
  return 'var(--score-low)';
}

export default function FinalistPanel({
  finalSelection,
  arrangements,
  selectedId,
  onSelect,
}: FinalistPanelProps) {
  const { selection_roles, selected_candidate_ids } = finalSelection;
  const toggleCuration = useArrangementStore((s) => s.toggleCuration);
  if (selected_candidate_ids.length === 0) return null;

  const arrLookup = new Map(arrangements.map((a) => [a.id, a]));

  return (
    <div style={{ borderBottom: '1px solid var(--border-default)', background: 'var(--surface-1)' }}>
      <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'var(--accent-primary)' }}
          />
          <h3
            className="text-xs font-semibold uppercase tracking-widest"
            style={{ color: 'var(--accent-primary)' }}
          >
            Finalists
          </h3>
        </div>
      </div>
      <div className="flex flex-col gap-1 p-2">
        {selected_candidate_ids.map((id) => {
          const arr = arrLookup.get(id);
          if (!arr) return null;
          const role = selection_roles[id];
          const config = ROLE_CONFIG[role] || { label: role, accent: 'var(--text-muted)' };
          const isSelected = selectedId === id;
          const isCurated = arr.is_curated ?? null;

          return (
            <div
              key={id}
              onClick={() => onSelect(id)}
              className="rounded-md p-3 cursor-pointer transition-all"
              style={{
                background: isSelected ? 'var(--surface-3)' : 'var(--surface-2)',
                borderLeft: isSelected ? `3px solid ${config.accent}` : '3px solid transparent',
                border: isSelected ? undefined : '1px solid var(--border-subtle)',
              }}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className="text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: `${config.accent}20`, color: config.accent, border: `1px solid ${config.accent}40` }}
                >
                  {config.label}
                </span>
                <div
                  className="flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <span
                    className="text-sm font-bold font-mono"
                    style={{ color: scoreColor(arr.weighted_total) }}
                  >
                    {(arr.weighted_total ?? 0).toFixed(2)}
                  </span>
                  <StarButton
                    isCurated={isCurated}
                    onToggle={(next) => {
                      void toggleCuration(id, next).catch(() => {
                        // Store already toasts on failure; swallow.
                      });
                    }}
                  />
                </div>
              </div>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{arr.rationale}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Note: `sessionId` prop is now unused. Check whether callers (`SessionWorkspace`, `ArrangementList`) still pass it — if they do, leave it on the interface but unused (preferred) or remove from interface + callers in the same commit. Keep scope tight; leave the prop.

- [ ] **Step 4: Verify pass**

```bash
cd frontend && npm test -- FinalistPanel
```
Expected: PASS.

- [ ] **Step 5: Run full frontend suite + tsc**

```bash
cd frontend && npm test && npx tsc --noEmit
```
Expected: all tests pass, no TS errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/FinalistPanel.tsx frontend/src/components/__tests__/FinalistPanel.test.tsx
git commit -m "feat(m5d-3): replace Save-to-library with per-finalist star on FinalistPanel"
```

---

## Part 8 — E2E

### Task 22: E2E curation flow

**Files:**
- Modify: `e2e/tests/pattern-library.spec.ts`

- [ ] **Step 1: Read existing E2E spec first**

```bash
cat e2e/tests/pattern-library.spec.ts
```

- [ ] **Step 2: Append a new `test()` block**

Append to `e2e/tests/pattern-library.spec.ts` inside the existing `test.describe` block:

```typescript
  test('curate a pattern, filter to curated-only, persist across reload', async ({ page, testSession }) => {
    // 1. Run a session to seed patterns.
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);
    await expect(page.locator('text=/Saved \\d+ patterns to library/').first())
      .toBeVisible({ timeout: 60_000 });

    // 2. Go to library, wait for first card.
    await page.goto('/patterns');
    const firstCard = page.locator('[data-testid^="pattern-card-"]').first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });
    const starredTestId = await firstCard.getAttribute('data-testid');
    expect(starredTestId).toBeTruthy();

    // 3. Click its star; expect the Curated toast.
    await firstCard.getByRole('button', { name: 'Mark as curated' }).click();
    await expect(page.locator('text=/^Curated$/').first())
      .toBeVisible({ timeout: 10_000 });

    // 4. Toggle the Curated-only filter on.
    await page.getByLabel('Curated only').check();

    // 5. Only curated items visible; our starred card is one of them.
    await expect(page.locator(`[data-testid="${starredTestId}"]`)).toBeVisible();
    await expect(
      page.locator(`[data-testid="${starredTestId}"]`)
        .getByRole('button', { name: 'Remove from curated' }),
    ).toBeVisible();

    // 6. Reload — filter state is user-selectable (may or may not persist in URL per
    //    implementation); we instead verify the DATA persists by re-checking the
    //    starred card, then re-enabling the filter, and asserting it still shows
    //    the starred row with filled star.
    await page.reload();
    const cardAfterReload = page.locator(`[data-testid="${starredTestId}"]`);
    await expect(cardAfterReload).toBeVisible({ timeout: 15_000 });
    await expect(
      cardAfterReload.getByRole('button', { name: 'Remove from curated' }),
    ).toBeVisible();
    await page.getByLabel('Curated only').check();
    await expect(cardAfterReload).toBeVisible();
  });
```

- [ ] **Step 3: Run E2E**

```bash
make e2e
```
Expected: both tests in the file pass.

- [ ] **Step 4: Commit**

```bash
git add e2e/tests/pattern-library.spec.ts
git commit -m "test(m5d-3): E2E — curate, filter, reload persistence"
```

---

## Part 9 — Migration, verification, handoff

### Task 23: Run the migration against dev Neo4j

- [ ] **Step 1: Confirm dev Neo4j is reachable**

```bash
cd backend && uv run python scripts/migrations/m5d3_curation_fields.py
```
Expected: prints dry-run Cypher; exits 0.

- [ ] **Step 2: Apply**

```bash
cd backend && uv run python scripts/migrations/m5d3_curation_fields.py --yes
```
Expected: reports row-count backfilled + index created.

- [ ] **Step 3: Spot-check**

```bash
cd backend && uv run python -c "
import asyncio
from explorator.graph.connection import get_driver
async def check():
    d = await get_driver()
    async with d.session() as s:
        result = await s.run(
            'MATCH (p:PatternLibraryEntry) WHERE p.is_curated IS NULL RETURN count(p) AS missing'
        )
        record = await result.single()
        print(f'rows with null is_curated: {record[\"missing\"]}')
        result = await s.run(\"SHOW INDEXES YIELD name WHERE name = 'user_feedback_event_type' RETURN name\")
        record = await result.single()
        print(f'feedback event index exists: {record is not None}')
    await d.close()
asyncio.run(check())
"
```
Expected:
```
rows with null is_curated: 0
feedback event index exists: True
```

---

### Task 24: Final suite + manual smoke

- [ ] **Step 1: Full backend suite**

```bash
cd backend && make test && make lint
```
Expected: previously-green tests remain green; mypy clean for new code (any pre-existing warnings carried over are acceptable — they predate this branch).

- [ ] **Step 2: Frontend suite + build**

```bash
cd frontend && npm test && npx tsc --noEmit && npm run build
```
Expected: all green, build succeeds.

- [ ] **Step 3: E2E**

```bash
make e2e
```
Expected: pattern-library.spec.ts (both tests) green; existing E2E tests untouched.

- [ ] **Step 4: Manual smoke**

Start full stack. Bind to 0.0.0.0 for both:

```bash
cd backend && uv run uvicorn explorator.api.app:app --host 0.0.0.0 --port 8100 --reload &
cd frontend && npm run dev -- --host 0.0.0.0 &
```

Smoke steps (manual, in browser):
1. Create a session, generate + realize to completion; watch for "Saved N patterns to library" toast.
2. Open the Finalists panel — confirm no "Save to library" button, and each finalist shows an outlined star next to its score.
3. Click a star; expect a "Curated" toast and the star to fill.
4. Navigate to `/patterns`; confirm the starred pattern's card has a filled star; others have outlined stars.
5. Toggle `Curated only`; confirm the list narrows to starred rows only.
6. Reload; confirm the starred row persists with its star filled.
7. Uncurate from `/patterns`; expect "Removed from curated" toast and outlined star.

- [ ] **Step 5: Clean up CLAUDE.md leftovers**

```bash
git status
# If subagent CLAUDE.md files appear modified/untracked, restore them before PR.
git checkout docs/superpowers/plans/CLAUDE.md docs/superpowers/specs/CLAUDE.md
rm -f backend/src/explorator/domain/memory/CLAUDE.md
```

- [ ] **Step 6: Push + open PR**

```bash
git push -u origin feature/m5d3-pattern-curation
gh pr create --title "feat(m5d-3): pattern curation" --body "$(cat <<'EOF'
## Summary
- Adds arrangement-level pattern curation — user-starred finalists surface in the library with a "Curated only" filter.
- Removes the redundant `Save to library` button from FinalistPanel in favor of per-finalist stars.
- Backend: new `is_curated`/`curated_at` on `PatternLibraryEntry`, atomic curation service (event + fan-out in one tx), `POST /v1/arrangements/{id}/curation` endpoint, `curated_only` filter on `GET /v1/patterns`, curation derivation on arrangement responses (nullable, single round-trip).

## Test plan
- [ ] `make test` — backend unit + integration + API green
- [ ] `npm test` (frontend) — all vitest green
- [ ] `make e2e` — both pattern-library spec tests green
- [ ] Manual smoke: curate → filter → reload → uncurate

Closes M5d-3 (spec: `docs/superpowers/specs/2026-04-20-m5d3-pattern-curation-design.md`).
EOF
)"
```

---

## Self-review checklist (done before handoff)

1. **Spec coverage — every §"§"Testing approach"§ bullet mapped to a task:**
   - Repo: `toggle_curation` (T5), upsert on-match (T4), `list_page curated_only` (T6), arrangement with soft-deleted facets (T5 `test_toggle_curation_skips_soft_deleted`), feedback repo roundtrip (T8), fetch_curation_state N+1 guard (T7).
   - API: POST happy path (T12), 404 (T12), 409 with no-event-and-WARN-log (T8+T12), body validation (T12), GET patterns curated_only (T10), GET patterns schema fields (T9), arrangement is_curated null/false/true (T11), arrangement N+1 guard (T7).
   - Frontend vitest: API client (T14), patternLibraryStore.toggleCuration (T16), arrangementStore.toggleCuration (T17), patternFiltersStore (T15), PatternCard (T19), FinalistPanel (T21), PatternFilters (T20).
   - E2E: curate → filter → reload (T22).
2. **Spec §"Mid-session timing" covered:** disabled star state in `StarButton` (T18), nullable `is_curated` on `ArrangementSummary` (T13), 409 with WARN log (T8 + T12).
3. **Spec §"Data model §`ON MATCH` exclusion":** regression test first (T4).
4. **Spec §"Migration":** idempotent backfill + index (T3, T23).
5. **Out-of-scope items deliberately not in tasks:** warm-start retrieval boost, taste model updates, bulk curate, negative signal, facet-level granularity, cross-tab live sync, analytics UI, batch backfill reconciliation, auto-curation of finalists.
6. **Placeholders:** none. Every step has code or exact commands.
7. **Type consistency:** `is_curated`/`curated_at` nullable on `ArrangementSummary`, non-null on `PatternItem`; `toggle_curation` signatures match between repo (`arrangement_id`, `is_curated`, `now`) and service (`arrangement_id`, `is_curated`).
