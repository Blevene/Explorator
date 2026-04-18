# M5d — Retrieval-Assisted Warm Starts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harvest reusable patterns (progression, voicing, bass, groove, melody) from finalist arrangements into a Neo4j-backed library, then offer those patterns as optional warm starts when the user creates a new session for the same genre.

**Architecture:** A new `PatternLibraryRepo` stores `PatternLibraryEntry` nodes keyed by a natural `(source_candidate_id, pattern_type)` pair so upsert is idempotent at the data layer. A `harvest_patterns` LangGraph node auto-runs between `persist_realization` and `persist_round`; each finalist arrangement is abstracted into typed patterns with auto-generated tags via a small `domain/memory/pattern_harvesting.py` module that factors common entity construction into a single `_build_entry` helper. A `load_warm_starts` node runs after `load_memory` and populates `state["warm_starts"]` with selected patterns. Warm-start injection is **strategy-level** for voicing/bass/groove/melody (seed a strategy, let the existing deterministic realizer produce events — avoiding the empty-event-list trap) and **pre-built candidate** for progression (chord sequences don't need realization). A new `patterns` FastAPI router exposes list/get/delete plus per-session warm-start suggestions and a manual "save finalists" endpoint. Frontend adds a `patternLibraryStore`, `WarmStartPanel` (pre-generation), `PatternLibraryBrowser` (with provenance link back to source session), a "Save to library" button in `FinalistPanel`, and Sonner toasts for auto-harvest feedback.

**Tech Stack:** Python 3.12, FastAPI, Neo4j (Cypher with MERGE natural-key upsert), LangGraph, Pydantic; React + TypeScript, Zustand, React Router, Sonner; Playwright for E2E.

---

## Design decisions locked before tasks begin

1. **Auto-harvest trigger** — `harvest_patterns` runs between `persist_realization` and `persist_round` (graph edge change). This runs once when the exploration loop's `check_stop` routes to `persist_realization` (final round only). "Finalists" = `final_selection.selected_candidate_ids` assigned `safest` / `best_loop` / `most_experimental` roles by `rank_and_select`. The manual "Save to library" button shares the same idempotent upsert path; repeated clicks refresh metadata but never duplicate rows.

2. **Idempotent upsert via Cypher MERGE on a natural key.** Repo `upsert()` uses `MERGE (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) ON CREATE SET p = $props, p.id = $id ON MATCH SET p += $props, p.updated_at = $now`. Re-harvesting the same finalist refreshes scores and tags without producing a duplicate. Auto-harvest and manual-harvest share this behavior — no separate in-Python dedupe needed.

3. **Warm-start injection mode — strategy-level for 4 of 5 types.**
   - **Progression:** pattern's chord sequence enters as candidate #1 (LLM generates `n_candidates - 1`). Option (a) — safe because progression candidates are leaf data.
   - **Voicing, Bass, Groove, Melody:** pattern's *strategy* (not a pre-built plan) is seeded. The existing deterministic realizer in each node consumes the seeded strategy and produces full event lists, so downstream evaluation gates receive well-formed artifacts. This avoids the empty-`voicings` / empty-`notes` trap.

4. **Genre source & reconciliation.** `POST /v1/sessions` gains an optional `genre` field, stored on the Session node as a top-level `genre` property (not inside the JSON metadata blob). `parse_intent` is updated to prefer an already-set `state["genre"]` over its own LLM inference — the user's Dashboard pick is authoritative when present.

5. **Session warm-start IDs — flat Neo4j array property.** `POST /v1/sessions/{id}/warm-starts` stores `warm_start_pattern_ids: list[str]` as a native Neo4j string-array property on the Session node (not inside the JSON metadata). Avoids the read-modify-write race on the metadata JSON blob.

6. **Toast** — Sonner (~3KB gzipped, one dependency). Mounted once in `App.tsx`. Used for the "N patterns saved to library" notification after auto-harvest and for manual-save confirmations.

7. **`RetrievalQuery` / `RetrievalResult` entities** — present as Pydantic models but not persisted in M5d. Retrieval is a direct function call; no Protocol abstraction ships (YAGNI — `VectorRetrieval` is a future refactor on a single call site).

8. **Vector-readiness** — `embedding: list[float] | None = None` field exists on `PatternLibraryEntry`, always `null` in M5d. A single `# TODO(vector)` comment marks the swap point for a future vector-backed retrieval path.

9. **Home for new domain code** — `backend/src/explorator/domain/memory/` (parallel to existing `domain/harmony/`, `domain/intent/`, etc.). No new `services/` top-level directory is created.

---

## File Structure

### Backend — create

| Path | Responsibility |
|------|---------------|
| `backend/src/explorator/domain/memory/__init__.py` | Package marker |
| `backend/src/explorator/domain/memory/pattern_harvesting.py` | `_build_entry` helper + 5 type-specific harvesters + `harvest_finalist` orchestrator + auto-tag rules |
| `backend/src/explorator/domain/memory/pattern_retrieval.py` | `fetch_warm_starts(genre, top_k_per_type, tag_filters)` function — single call site, no Protocol |
| `backend/src/explorator/graph/pattern_library_repo.py` | Neo4j CRUD (MERGE natural-key upsert, get, list, delete, query) |
| `backend/src/explorator/engine/nodes/harvest_patterns.py` | LangGraph node — auto-harvest with per-entry try/except |
| `backend/src/explorator/engine/nodes/load_warm_starts.py` | LangGraph node — loads patterns with `asyncio.wait_for` timeout |
| `backend/src/explorator/api/routes/patterns.py` | FastAPI router — all pattern-related endpoints |
| `backend/src/explorator/constants.py` (if missing) or extend existing | `PATTERN_TYPES: tuple[str, ...] = ("progression", "voicing", "bass", "groove", "melody")` |
| `backend/tests/domain/memory/__init__.py` | |
| `backend/tests/domain/memory/test_pattern_harvesting.py` | |
| `backend/tests/domain/memory/test_pattern_retrieval.py` | |
| `backend/tests/graph/test_pattern_library_repo.py` | |
| `backend/tests/engine/nodes/test_harvest_patterns.py` | |
| `backend/tests/engine/nodes/test_load_warm_starts.py` | |
| `backend/tests/api/test_patterns_router.py` | |

### Backend — modify

| Path | Change |
|------|--------|
| `backend/src/explorator/models/memory.py` | Add `embedding: list[float] \| None = None`; make `source_candidate_id: str` required |
| `backend/src/explorator/graph/schema.py` | Add composite index `(genre, pattern_type)` + scalar index on a new denormalized `weighted_total` property |
| `backend/src/explorator/api/deps.py` | Add `get_pattern_library_repo` provider |
| `backend/src/explorator/api/app.py` | Register `patterns.router` |
| `backend/src/explorator/api/routes/sessions.py` | Accept optional `genre` on `CreateSessionRequest`; store as top-level `Session.genre` property; expose `warm_start_pattern_ids` on responses |
| `backend/src/explorator/api/routes/rounds.py` | Read `genre` + `warm_start_pattern_ids` from Session top-level properties; pass into `initial_state` |
| `backend/src/explorator/engine/state.py` | Add `warm_start_pattern_ids`, `warm_starts`, `harvested_pattern_ids` fields |
| `backend/src/explorator/engine/graph.py` | Register `load_warm_starts` (after `load_memory`); register `harvest_patterns` (between `persist_realization` and `persist_round`) |
| `backend/src/explorator/engine/nodes/parse_intent.py` | Prefer pre-set `state["genre"]` over LLM inference |
| `backend/src/explorator/engine/nodes/generate.py` | Prepend progression warm-start as candidate #1; reduce LLM count by seed count |
| `backend/src/explorator/engine/nodes/plan_voicings.py` | Accept a seeded strategy via `state["warm_starts"]["voicing"]` — inject into the existing strategies list before realization |
| `backend/src/explorator/engine/nodes/generate_bass.py` | Same strategy-seed pattern for bass |
| `backend/src/explorator/engine/nodes/generate_groove.py` | Same strategy-seed pattern for groove |
| `backend/src/explorator/engine/nodes/generate_melody.py` | Same strategy-seed pattern for melody |
| `backend/tests/conftest.py` (root) | Add `seed_patterns`, `seeded_house_session`, `completed_session` fixtures |

### Frontend — create

| Path | Responsibility |
|------|---------------|
| `frontend/src/stores/patternLibraryStore.ts` | Zustand store |
| `frontend/src/components/WarmStartPanel.tsx` | Pre-submit warm-start selector |
| `frontend/src/components/PatternLibraryBrowser.tsx` | Library viewer with filters, delete, provenance link |
| `frontend/src/components/toastWrapper.ts` | Sonner wrapper |
| `frontend/src/constants/patternTypes.ts` | Mirror of backend `PATTERN_TYPES` |
| `e2e/tests/warm-starts.spec.ts` | 5 Playwright tests |

### Frontend — modify

| Path | Change |
|------|--------|
| `frontend/package.json` | Add `sonner` |
| `frontend/src/App.tsx` | Mount `<Toaster />`; add `/patterns` route |
| `frontend/src/services/api.ts` | Add pattern API client functions with shared `PatternItem` interface |
| `frontend/src/views/Dashboard.tsx` | Genre selector + `WarmStartPanel` wiring; `/patterns` nav link |
| `frontend/src/components/FinalistPanel.tsx` | "Save finalists to library" button |
| `frontend/src/components/SessionWorkspace.tsx` | SSE handler for `pattern_harvest` event → toast |

---

## Phase 1 — Data model, schema, legacy cleanup

### Task 1: Update `PatternLibraryEntry` model

**Files:**
- Modify: `backend/src/explorator/models/memory.py`
- Create: `backend/tests/models/test_memory.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/models/test_memory.py`:

```python
"""Tests for memory-related Pydantic models."""
from datetime import datetime, UTC
import pytest
from pydantic import ValidationError

from explorator.models.memory import PatternLibraryEntry


def _now() -> datetime:
    return datetime.now(UTC)


def test_pattern_library_entry_requires_source_candidate_id():
    with pytest.raises(ValidationError):
        PatternLibraryEntry(
            id="pl_01", type="pattern_library_entry",
            created_at=_now(), updated_at=_now(),
            status="active", metadata={},
            pattern_type="progression", genre="house",
        )


def test_pattern_library_entry_embedding_defaults_to_none():
    entry = PatternLibraryEntry(
        id="pl_01", type="pattern_library_entry",
        created_at=_now(), updated_at=_now(),
        status="active", metadata={},
        pattern_type="progression", genre="house",
        source_candidate_id="arr_01",
    )
    assert entry.embedding is None


def test_pattern_library_entry_accepts_embedding_list():
    entry = PatternLibraryEntry(
        id="pl_01", type="pattern_library_entry",
        created_at=_now(), updated_at=_now(),
        status="active", metadata={},
        pattern_type="progression", genre="house",
        source_candidate_id="arr_01",
        embedding=[0.1, 0.2, 0.3],
    )
    assert entry.embedding == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run, verify failure**

`cd backend && uv run pytest tests/models/test_memory.py -v` → FAIL (embedding missing, source_candidate_id still nullable).

- [ ] **Step 3: Implement**

Edit `backend/src/explorator/models/memory.py`:

```python
class PatternLibraryEntry(BaseEntity):
    """Reusable pattern harvested from a finalist arrangement."""

    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    # TODO(vector): when embeddings ship, populate from an embedder service and
    # swap GraphRetrieval for a vector-backed retrieval in fetch_warm_starts.
    embedding: list[float] | None = None
```

- [ ] **Step 4: Run**

`cd backend && uv run pytest tests/models/test_memory.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/memory.py backend/tests/models/test_memory.py
git commit -m "feat(m5d): require source_candidate_id, add embedding to PatternLibraryEntry"
```

---

### Task 2: Add Neo4j schema indexes + uniqueness constraint

**Files:**
- Modify: `backend/src/explorator/graph/schema.py`

- [ ] **Step 1: Inspect current schema**

Run: `cd backend && grep -n "pattern_library" src/explorator/graph/schema.py` — expect one existing line.

- [ ] **Step 2: Replace with M5d set**

Replace the existing `pattern_library_genre` line with:

```python
# M5d: PatternLibraryEntry indexes + natural-key uniqueness
"CREATE INDEX pattern_library_genre IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.genre)",
"CREATE INDEX pattern_library_genre_type IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.genre, n.pattern_type)",
"CREATE INDEX pattern_library_weighted_total IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.weighted_total)",
"CREATE CONSTRAINT pattern_library_natural_key IF NOT EXISTS FOR (n:PatternLibraryEntry) REQUIRE (n.source_candidate_id, n.pattern_type) IS UNIQUE",
```

The natural-key constraint enforces idempotent upsert at the DB layer — `MERGE` with the same `(source_candidate_id, pattern_type)` pair will match an existing row.

The `weighted_total` index is on a denormalized top-level scalar property (Task 3's repo writes it alongside the JSON `success_metrics` blob) so retrieval can `ORDER BY weighted_total DESC` at the Cypher level.

- [ ] **Step 3: Apply**

`cd backend && uv run python -c "import asyncio; from explorator.graph.schema import apply_schema; from explorator.adapters.neo4j_client import get_driver; asyncio.run(apply_schema(get_driver()))"` → no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/graph/schema.py
git commit -m "feat(m5d): pattern_library indexes + natural-key uniqueness constraint"
```

---

### Task 3: Legacy `PatternLibraryEntry` cleanup migration

**Files:**
- Create: `backend/scripts/migrations/m5d_cleanup_stub_patterns.py`

- [ ] **Step 1: Write migration script**

```python
"""M5d migration: remove any stub PatternLibraryEntry rows with null source_candidate_id.

Pre-M5d, the model had `source_candidate_id: str | None = None`. M5d makes it required.
Any null-valued rows in dev/test Neo4j instances will fail Pydantic validation on read.
This script is idempotent and safe to run on clean databases (zero rows affected).
"""
import asyncio
from explorator.adapters.neo4j_client import get_driver


async def main() -> None:
    driver = get_driver()
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "MATCH (p:PatternLibraryEntry) WHERE p.source_candidate_id IS NULL "
            "DETACH DELETE p RETURN count(p) AS removed"
        )
        record = await result.single()
        print(f"Removed {record['removed']} legacy PatternLibraryEntry rows")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the migration**

`cd backend && uv run python scripts/migrations/m5d_cleanup_stub_patterns.py`
Expected: prints `Removed 0 legacy PatternLibraryEntry rows` on a clean DB; any positive number is also acceptable (pre-existing stub rows cleaned up).

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/migrations/m5d_cleanup_stub_patterns.py
git commit -m "chore(m5d): migration to remove legacy null-source stub patterns"
```

---

### Task 4: Add `PATTERN_TYPES` constant (backend)

**Files:**
- Modify or create: `backend/src/explorator/constants.py`

- [ ] **Step 1: Check if constants.py exists**

`ls backend/src/explorator/constants.py` — if missing, create; else append.

- [ ] **Step 2: Add the tuple**

```python
# M5d: canonical list of pattern types. Any change here must be mirrored in
# frontend/src/constants/patternTypes.ts.
PATTERN_TYPES: tuple[str, ...] = ("progression", "voicing", "bass", "groove", "melody")
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/constants.py
git commit -m "feat(m5d): add PATTERN_TYPES constant"
```

---

## Phase 2 — Neo4j repository

### Task 5: `PatternLibraryRepo` with MERGE-on-natural-key upsert

**Files:**
- Create: `backend/src/explorator/graph/pattern_library_repo.py`
- Create: `backend/tests/graph/test_pattern_library_repo.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for PatternLibraryRepo."""
from datetime import datetime, UTC
import pytest

from explorator.models.memory import PatternLibraryEntry
from explorator.graph.pattern_library_repo import PatternLibraryRepo


def _entry(
    *, pattern_id: str = "pl_abc", source: str = "arr_01",
    ptype: str = "progression", genre: str = "house",
    weighted_total: float = 0.82,
) -> PatternLibraryEntry:
    now = datetime.now(UTC)
    return PatternLibraryEntry(
        id=pattern_id, type="pattern_library_entry",
        created_at=now, updated_at=now, status="active", metadata={},
        pattern_type=ptype, genre=genre,
        tags=["role:safest"],
        source_candidate_id=source,
        abstracted_pattern={"chord_symbols": ["C", "F", "G", "C"]},
        success_metrics={"weighted_total": weighted_total, "loopability": 0.9},
    )


@pytest.mark.asyncio
async def test_upsert_and_get(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry())
    fetched = await repo.get_by_id("pl_abc")
    assert fetched is not None
    assert fetched["pattern_type"] == "progression"
    assert fetched["tags"] == ["role:safest"]
    assert fetched["abstracted_pattern"]["chord_symbols"] == ["C", "F", "G", "C"]
    assert fetched["weighted_total"] == pytest.approx(0.82)  # denormalized scalar


@pytest.mark.asyncio
async def test_upsert_idempotent_on_natural_key(neo4j_driver):
    """Two upserts with same (source_candidate_id, pattern_type) but different ids
    must result in exactly one row — the second call MATCHES instead of CREATING."""
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_first", weighted_total=0.5))
    await repo.upsert(_entry(pattern_id="pl_second", weighted_total=0.9))
    all_rows = await repo.list_all(genre="house", pattern_type="progression")
    assert len(all_rows) == 1
    # ON MATCH SET p += $props merges in the newer props (including weighted_total)
    assert all_rows[0]["weighted_total"] == pytest.approx(0.9)
    # The id is whichever was created first (ON CREATE SET p.id = $id)
    assert all_rows[0]["id"] == "pl_first"


@pytest.mark.asyncio
async def test_delete_by_id(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry())
    await repo.delete_by_id("pl_abc")
    assert await repo.get_by_id("pl_abc") is None


@pytest.mark.asyncio
async def test_list_all_filters_by_genre_and_type(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_1", source="arr_1", ptype="progression", genre="house"))
    await repo.upsert(_entry(pattern_id="pl_2", source="arr_2", ptype="voicing", genre="house"))
    await repo.upsert(_entry(pattern_id="pl_3", source="arr_3", ptype="progression", genre="techno"))

    assert len(await repo.list_all(genre="house")) == 2
    assert len(await repo.list_all(genre="house", pattern_type="progression")) == 1
    assert len(await repo.list_all(genre="techno")) == 1


@pytest.mark.asyncio
async def test_list_all_filters_by_tags(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    e1 = _entry(pattern_id="pl_1", source="arr_1")
    e1.tags = ["role:safest", "loopability_high"]
    e2 = _entry(pattern_id="pl_2", source="arr_2")
    e2.tags = ["role:most_experimental", "loopability_high"]
    await repo.upsert(e1)
    await repo.upsert(e2)

    safest = await repo.list_all(genre="house", tags=["role:safest"])
    assert len(safest) == 1 and safest[0]["id"] == "pl_1"

    high = await repo.list_all(genre="house", tags=["loopability_high"])
    assert len(high) == 2


@pytest.mark.asyncio
async def test_query_for_warm_starts_orders_by_weighted_total(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_low", source="arr_low", weighted_total=0.5))
    await repo.upsert(_entry(pattern_id="pl_high", source="arr_high", weighted_total=0.9))
    await repo.upsert(_entry(pattern_id="pl_mid", source="arr_mid", weighted_total=0.7))

    grouped = await repo.query_for_warm_starts(genre="house", top_k_per_type=2)

    assert [e["id"] for e in grouped["progression"]] == ["pl_high", "pl_mid"]


@pytest.mark.asyncio
async def test_query_for_warm_starts_applies_tag_filters(neo4j_driver):
    """tag_filters narrows results within each pattern_type bucket."""
    repo = PatternLibraryRepo(neo4j_driver)
    e1 = _entry(pattern_id="pl_1", source="arr_1", weighted_total=0.9)
    e1.tags = ["role:safest"]
    e2 = _entry(pattern_id="pl_2", source="arr_2", weighted_total=0.8)
    e2.tags = ["role:most_experimental"]
    await repo.upsert(e1)
    await repo.upsert(e2)

    grouped = await repo.query_for_warm_starts(
        genre="house", top_k_per_type=5, tag_filters=["role:safest"]
    )
    assert [e["id"] for e in grouped.get("progression", [])] == ["pl_1"]
```

- [ ] **Step 2: Run**

`cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/src/explorator/graph/pattern_library_repo.py`:

```python
"""Neo4j repository for PatternLibraryEntry (M5d)."""
from typing import Any

from neo4j import AsyncDriver

from explorator.graph.repository import _neo4j_safe, _neo4j_deserialize
from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now


class PatternLibraryRepo:
    """CRUD and query access for pattern library entries.

    Idempotence is enforced at the DB layer via a uniqueness constraint on
    (source_candidate_id, pattern_type); upsert uses MERGE on that natural key.
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def upsert(self, entry: PatternLibraryEntry) -> None:
        """Create or update by (source_candidate_id, pattern_type). ULID is set
        only on first create; subsequent upserts refresh props in place."""
        payload = entry.model_dump(mode="json")
        weighted_total = float((payload.get("success_metrics") or {}).get("weighted_total") or 0.0)
        props = _neo4j_safe({k: v for k, v in payload.items() if k not in ("id", "source_candidate_id", "pattern_type")})
        props["weighted_total"] = weighted_total  # denormalized scalar for indexed ORDER BY

        query = """
        MERGE (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt})
        ON CREATE SET p = $props, p.id = $id, p.source_candidate_id = $scid, p.pattern_type = $pt
        ON MATCH  SET p += $props, p.updated_at = $updated_at
        """
        async with self._driver.session() as neo_session:
            await neo_session.run(
                query,
                scid=entry.source_candidate_id, pt=entry.pattern_type,
                id=entry.id, props=props,
                updated_at=utc_now().isoformat(),
            )

    async def get_by_id(self, entry_id: str) -> dict[str, Any] | None:
        query = "MATCH (p:PatternLibraryEntry {id: $id}) RETURN p"
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, id=entry_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["p"]))

    async def list_all(
        self,
        *,
        genre: str | None = None,
        pattern_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if genre is not None:
            clauses.append("p.genre = $genre")
            params["genre"] = genre
        if pattern_type is not None:
            clauses.append("p.pattern_type = $pattern_type")
            params["pattern_type"] = pattern_type
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"""
        MATCH (p:PatternLibraryEntry)
        {where}
        RETURN p
        ORDER BY p.weighted_total DESC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            records = [r async for r in result]
        entries = [_neo4j_deserialize(dict(rec["p"])) for rec in records]

        # Tags are stored as a JSON string; filter in Python at small cardinality.
        if tags:
            entries = [e for e in entries if all(t in (e.get("tags") or []) for t in tags)]
        return entries

    async def delete_by_id(self, entry_id: str) -> None:
        query = "MATCH (p:PatternLibraryEntry {id: $id}) DETACH DELETE p"
        async with self._driver.session() as neo_session:
            await neo_session.run(query, id=entry_id)

    async def query_for_warm_starts(
        self,
        *,
        genre: str,
        top_k_per_type: int = 5,
        tag_filters: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top-K patterns per pattern_type for a genre, ordered by weighted_total DESC."""
        all_for_genre = await self.list_all(genre=genre, tags=tag_filters)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in all_for_genre:
            grouped.setdefault(entry["pattern_type"], []).append(entry)
        # list_all already orders by weighted_total DESC — just truncate per bucket.
        for ptype, bucket in grouped.items():
            grouped[ptype] = bucket[:top_k_per_type]
        return grouped
```

- [ ] **Step 4: Run**

`cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/graph/test_pattern_library_repo.py
git commit -m "feat(m5d): PatternLibraryRepo with MERGE-on-natural-key upsert + tag_filters retrieval"
```

---

## Phase 3 — Pattern harvesting service

### Task 6: `_build_entry` helper + progression harvester

**Files:**
- Create: `backend/src/explorator/domain/memory/__init__.py`
- Create: `backend/src/explorator/domain/memory/pattern_harvesting.py`
- Create: `backend/tests/domain/memory/__init__.py`
- Create: `backend/tests/domain/memory/test_pattern_harvesting.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for pattern harvesting abstractions and tag generation."""
from explorator.domain.memory.pattern_harvesting import harvest_progression_pattern


def _arrangement(arr_id: str = "arr_01") -> dict:
    return {"id": arr_id, "progression_candidate_id": "prog_01"}


def _progression(
    chord_symbols: list[str] | None = None,
    roman_numerals: list[str] | None = None,
    bars: int = 4,
) -> dict:
    return {
        "id": "prog_01",
        "key_center": "C",
        "mode": "major",
        "chord_symbols": chord_symbols or ["Cmaj7", "Am7", "Dm7", "G7"],
        "phrase_length_bars": bars,
        "metadata": {"roman_numerals": roman_numerals or ["Imaj7", "vi7", "ii7", "V7"]},
    }


def _scorecard(weighted: float = 0.8, loopability: float = 0.85, pareto: bool = False) -> dict:
    scores = {"loopability": loopability, "cadence_quality": 0.85, "theoretical_coherence": 0.75}
    return {
        "weighted_total": weighted,
        "scores": scores,
        "pareto_tags": ["pareto_front"] if pareto else [],
    }


def test_harvest_progression_basic_fields():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "progression"
    assert entry.genre == "house"
    assert entry.source_candidate_id == "arr_01"
    assert entry.abstracted_pattern["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    assert entry.abstracted_pattern["roman_numerals"] == ["Imaj7", "vi7", "ii7", "V7"]
    assert entry.success_metrics["weighted_total"] == 0.8


def test_harvest_progression_role_and_loopability_tags():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(loopability=0.2), genre="house", role="best_loop",
    )
    assert "role:best_loop" in entry.tags
    assert "loopability_low" in entry.tags


def test_harvest_progression_cadence_tag_authentic():
    """V → I (or V7 → Imaj7) final two chords → cadence:authentic."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["Imaj7", "vi7", "V7", "Imaj7"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:authentic" in entry.tags


def test_harvest_progression_cadence_tag_plagal():
    """IV → I final two → cadence:plagal."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["I", "vi", "IV", "I"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:plagal" in entry.tags


def test_harvest_progression_cadence_tag_half():
    """X → V final two → cadence:half."""
    entry = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(roman_numerals=["I", "vi", "ii", "V"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "cadence:half" in entry.tags


def test_harvest_progression_complexity_tag_buckets():
    """Complexity is bucketed by distinct-chord count: <=3 low, 4-5 mid, >=6 high."""
    low = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(chord_symbols=["C", "F", "C", "F"], roman_numerals=["I", "IV", "I", "IV"]),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    high = harvest_progression_pattern(
        arrangement=_arrangement(),
        progression=_progression(
            chord_symbols=["C", "Am", "F", "G", "Em", "Dm", "G7"],
            roman_numerals=["I", "vi", "IV", "V", "iii", "ii", "V7"],
        ),
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert "complexity:low" in low.tags
    assert "complexity:high" in high.tags


def test_harvest_progression_pareto_tag_propagates():
    entry = harvest_progression_pattern(
        arrangement=_arrangement(), progression=_progression(),
        scorecard=_scorecard(pareto=True), genre="house", role="safest",
    )
    assert "pareto_front" in entry.tags
```

- [ ] **Step 2: Run**

`cd backend && uv run pytest tests/domain/memory/test_pattern_harvesting.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

Create `backend/src/explorator/domain/memory/__init__.py` (empty).

Create `backend/src/explorator/domain/memory/pattern_harvesting.py`:

```python
"""Pattern harvesting — abstracts finalist facets into PatternLibraryEntry rows."""
from typing import Any

from ulid import ULID

from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now


# --- Tag helpers -----------------------------------------------------------------

def _bucket(value: float, low: float = 0.4, high: float = 0.7) -> str:
    if value >= high:
        return "high"
    if value >= low:
        return "mid"
    return "low"


def _loopability_tag(value: float) -> str:
    return f"loopability_{_bucket(value)}"


def _cadence_tag(roman_numerals: list[str]) -> str | None:
    """Classify final two Roman numerals as authentic/plagal/half/deceptive/unknown."""
    if len(roman_numerals) < 2:
        return None
    penult, final = _root_only(roman_numerals[-2]), _root_only(roman_numerals[-1])
    if penult in ("V", "v") and final in ("I", "i"):
        return "cadence:authentic"
    if penult in ("IV", "iv") and final in ("I", "i"):
        return "cadence:plagal"
    if final in ("V", "v"):
        return "cadence:half"
    if penult in ("V", "v"):  # V → not-I (deceptive, e.g. V→vi)
        return "cadence:deceptive"
    return "cadence:other"


def _root_only(roman: str) -> str:
    """Strip qualities/extensions ('Imaj7' → 'I', 'V7' → 'V', 'vi7' → 'vi')."""
    result: list[str] = []
    for ch in roman:
        if ch.isalpha() or ch in ("b", "#"):
            if ch.isdigit():
                break
            result.append(ch)
        else:
            break
    return "".join(result).rstrip("oø+")


def _complexity_tag(distinct_chords: int) -> str:
    if distinct_chords >= 6:
        return "complexity:high"
    if distinct_chords >= 4:
        return "complexity:mid"
    return "complexity:low"


def _range_tag(semitones: int) -> str:
    if semitones >= 19:
        return "range:wide"
    if semitones >= 12:
        return "range:medium"
    return "range:narrow"


# --- Entity builder --------------------------------------------------------------

def _new_id() -> str:
    return f"pl_{ULID()}"


def _build_entry(
    *,
    pattern_type: str,
    arrangement: dict[str, Any],
    abstracted: dict[str, Any],
    tags: list[str],
    scorecard: dict[str, Any],
    genre: str,
) -> PatternLibraryEntry:
    """Shared constructor for all 5 per-type harvesters."""
    scores = scorecard.get("scores") or {}
    wt = scorecard.get("weighted_total")
    success_metrics: dict[str, float] = {
        "weighted_total": float(wt) if isinstance(wt, (int, float)) else 0.0,
        **{k: float(v) for k, v in scores.items() if isinstance(v, (int, float))},
    }
    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now, updated_at=now,
        status="active", metadata={},
        pattern_type=pattern_type,
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern=abstracted,
        success_metrics=success_metrics,
    )


# --- Per-type harvesters ---------------------------------------------------------

def harvest_progression_pattern(
    *,
    arrangement: dict[str, Any],
    progression: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    scores = scorecard.get("scores") or {}
    romans = (progression.get("metadata") or {}).get("roman_numerals") or []
    chord_symbols = progression.get("chord_symbols") or []

    tags: list[str] = [
        f"role:{role}",
        _loopability_tag(scores.get("loopability", 0.0)),
        _complexity_tag(len(set(chord_symbols))),
    ]
    if (cad := _cadence_tag(romans)) is not None:
        tags.append(cad)
    if "pareto_front" in (scorecard.get("pareto_tags") or []):
        tags.append("pareto_front")

    abstracted = {
        "key_center": progression.get("key_center"),
        "mode": progression.get("mode"),
        "chord_symbols": chord_symbols,
        "roman_numerals": romans,
        "phrase_length_bars": progression.get("phrase_length_bars"),
    }
    return _build_entry(
        pattern_type="progression", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )
```

- [ ] **Step 4: Run**

`cd backend && uv run pytest tests/domain/memory/test_pattern_harvesting.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/memory/__init__.py backend/src/explorator/domain/memory/pattern_harvesting.py backend/tests/domain/memory/
git commit -m "feat(m5d): _build_entry helper + progression harvester with cadence/complexity tags"
```

---

### Task 7: Voicing, bass, groove, melody harvesters (use helper)

**Files:**
- Modify: `backend/src/explorator/domain/memory/pattern_harvesting.py`
- Modify: `backend/tests/domain/memory/test_pattern_harvesting.py`

- [ ] **Step 1: Append tests for all four**

```python
from explorator.domain.memory.pattern_harvesting import (
    harvest_voicing_pattern,
    harvest_bass_pattern,
    harvest_groove_pattern,
    harvest_melody_pattern,
)


def test_harvest_voicing_tags_and_abstracted():
    arr = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    vp = {"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}
    entry = harvest_voicing_pattern(
        arrangement=arr, voicing_plan=vp, scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "voicing"
    assert entry.abstracted_pattern == {"register_profile": "mid", "density": "medium", "voice_count": 4}
    assert {"role:safest", "register:mid", "density:medium", "voices:4"} <= set(entry.tags)


def test_harvest_bass_tags_and_abstracted():
    arr = {"id": "arr_01", "bass_line_id": "bl_01"}
    bl = {"id": "bl_01", "mode": "walking", "rhythmic_density": 0.65}
    entry = harvest_bass_pattern(
        arrangement=arr, bass_line=bl, scorecard=_scorecard(), genre="house", role="best_loop",
    )
    assert entry.pattern_type == "bass"
    assert entry.abstracted_pattern == {"mode": "walking", "rhythmic_density": 0.65}
    assert {"role:best_loop", "bass_mode:walking", "rhythmic_density:mid"} <= set(entry.tags)


def test_harvest_groove_tags_and_abstracted():
    arr = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    g = {"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    entry = harvest_groove_pattern(
        arrangement=arr, groove=g, scorecard=_scorecard(), genre="house", role="safest",
    )
    assert entry.pattern_type == "groove"
    assert entry.abstracted_pattern == {"swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    assert {"swing:mid", "syncopation:mid", "density:high", "template:house_basic"} <= set(entry.tags)


def test_harvest_melody_tags_and_abstracted():
    arr = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    m = {"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}
    entry = harvest_melody_pattern(
        arrangement=arr, melody=m, scorecard=_scorecard(), genre="house", role="most_experimental",
    )
    assert entry.pattern_type == "melody"
    assert entry.abstracted_pattern == {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}
    assert {"role:most_experimental", "contour:arch", "range:medium", "melody_density:mid"} <= set(entry.tags)
```

- [ ] **Step 2: Run** — expect FAIL.

- [ ] **Step 3: Implement four harvesters**

Append to `backend/src/explorator/domain/memory/pattern_harvesting.py`:

```python
def harvest_voicing_pattern(
    *, arrangement: dict[str, Any], voicing_plan: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    strategy = voicing_plan.get("strategy") or {}
    register = strategy.get("register_profile", "mid")
    density = strategy.get("density", "medium")
    voice_count = strategy.get("voice_count", 4)
    tags = [f"role:{role}", f"register:{register}", f"density:{density}", f"voices:{voice_count}"]
    abstracted = {"register_profile": register, "density": density, "voice_count": voice_count}
    return _build_entry(
        pattern_type="voicing", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_bass_pattern(
    *, arrangement: dict[str, Any], bass_line: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    mode = bass_line.get("mode", "root")
    density = float(bass_line.get("rhythmic_density", 0.5))
    tags = [f"role:{role}", f"bass_mode:{mode}", f"rhythmic_density:{_bucket(density)}"]
    abstracted = {"mode": mode, "rhythmic_density": density}
    return _build_entry(
        pattern_type="bass", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_groove_pattern(
    *, arrangement: dict[str, Any], groove: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    swing = float(groove.get("swing_level", 0.0))
    sync = float(groove.get("syncopation_level", 0.0))
    density = float(groove.get("density", 0.5))
    template = groove.get("template_name", "")
    tags = [
        f"role:{role}",
        f"swing:{_bucket(swing)}",
        f"syncopation:{_bucket(sync)}",
        f"density:{_bucket(density)}",
    ]
    if template:
        tags.append(f"template:{template}")
    abstracted = {
        "swing_level": swing, "syncopation_level": sync,
        "density": density, "template_name": template,
    }
    return _build_entry(
        pattern_type="groove", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )


def harvest_melody_pattern(
    *, arrangement: dict[str, Any], melody: dict[str, Any],
    scorecard: dict[str, Any], genre: str, role: str,
) -> PatternLibraryEntry:
    strategy = melody.get("strategy") or {}
    contour = strategy.get("contour_type", "")
    rng = int(strategy.get("range_semitones", 12))
    density = float(strategy.get("rhythmic_density", 0.5))
    tags = [
        f"role:{role}",
        f"contour:{contour}",
        _range_tag(rng),
        f"melody_density:{_bucket(density)}",
    ]
    abstracted = {"contour_type": contour, "range_semitones": rng, "rhythmic_density": density}
    return _build_entry(
        pattern_type="melody", arrangement=arrangement,
        abstracted=abstracted, tags=tags, scorecard=scorecard, genre=genre,
    )
```

- [ ] **Step 4: Run** → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/memory/pattern_harvesting.py backend/tests/domain/memory/test_pattern_harvesting.py
git commit -m "feat(m5d): voicing/bass/groove/melody harvesters sharing _build_entry helper"
```

---

### Task 8: `harvest_finalist` orchestrator

**Files:**
- Modify: `backend/src/explorator/domain/memory/pattern_harvesting.py`
- Modify: `backend/tests/domain/memory/test_pattern_harvesting.py`

- [ ] **Step 1: Test**

```python
from explorator.domain.memory.pattern_harvesting import harvest_finalist


def test_harvest_finalist_produces_one_entry_per_present_facet():
    arr = {
        "id": "arr_01", "progression_candidate_id": "prog_01",
        "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
        "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01",
    }
    entries = harvest_finalist(
        arrangement=arr,
        progression=_progression(),
        voicing_plan={"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}},
        bass_line={"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6},
        groove={"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.5, "density": 0.7, "template_name": "house_basic"},
        melody={"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}},
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert sorted(e.pattern_type for e in entries) == ["bass", "groove", "melody", "progression", "voicing"]


def test_harvest_finalist_skips_missing_facets():
    arr = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    entries = harvest_finalist(
        arrangement=arr, progression=_progression(),
        voicing_plan=None, bass_line=None, groove=None, melody=None,
        scorecard=_scorecard(), genre="house", role="safest",
    )
    assert [e.pattern_type for e in entries] == ["progression"]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Append to `pattern_harvesting.py`:

```python
def harvest_finalist(
    *, arrangement: dict[str, Any], progression: dict[str, Any],
    voicing_plan: dict[str, Any] | None, bass_line: dict[str, Any] | None,
    groove: dict[str, Any] | None, melody: dict[str, Any] | None,
    scorecard: dict[str, Any], genre: str, role: str,
) -> list[PatternLibraryEntry]:
    entries: list[PatternLibraryEntry] = [
        harvest_progression_pattern(
            arrangement=arrangement, progression=progression,
            scorecard=scorecard, genre=genre, role=role,
        )
    ]
    if voicing_plan is not None:
        entries.append(harvest_voicing_pattern(
            arrangement=arrangement, voicing_plan=voicing_plan,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if bass_line is not None:
        entries.append(harvest_bass_pattern(
            arrangement=arrangement, bass_line=bass_line,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if groove is not None:
        entries.append(harvest_groove_pattern(
            arrangement=arrangement, groove=groove,
            scorecard=scorecard, genre=genre, role=role,
        ))
    if melody is not None:
        entries.append(harvest_melody_pattern(
            arrangement=arrangement, melody=melody,
            scorecard=scorecard, genre=genre, role=role,
        ))
    return entries
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/memory/pattern_harvesting.py backend/tests/domain/memory/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest_finalist orchestrator"
```

---

## Phase 4 — Harvest LangGraph node + wiring

### Task 9: Extend `ExplorationState`

**Files:**
- Modify: `backend/src/explorator/engine/state.py`

- [ ] **Step 1: Append fields**

```python
    # --- M5d: Retrieval-Assisted Warm Starts ---
    warm_start_pattern_ids: list[str]
    warm_starts: dict[str, list[dict[str, Any]]]
    harvested_pattern_ids: list[str]
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/explorator/engine/state.py
git commit -m "feat(m5d): add warm-start and harvest fields to ExplorationState"
```

---

### Task 10: `harvest_patterns` node with per-entry error isolation

**Files:**
- Create: `backend/src/explorator/engine/nodes/harvest_patterns.py`
- Create: `backend/tests/engine/nodes/test_harvest_patterns.py`

- [ ] **Step 1: Tests**

```python
"""Tests for harvest_patterns LangGraph node."""
import logging
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.harvest_patterns import harvest_patterns


def _state_with_one_finalist() -> dict:
    return {
        "session_id": "sess_01",
        "genre": "house",
        "final_selection": {
            "selected_candidate_ids": ["arr_01"],
            "selection_roles": {"arr_01": "safest"},
        },
        "arrangement_candidates": [{
            "id": "arr_01",
            "progression_candidate_id": "prog_01",
            "voicing_plan_id": "vp_01",
            "bass_line_id": "bl_01",
            "groove_pattern_id": "gp_01",
            "melodic_complement_id": "mc_01",
        }],
        "progression_candidates": [{
            "id": "prog_01", "key_center": "C", "mode": "major",
            "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4,
            "metadata": {"roman_numerals": ["I", "IV", "V", "I"]},
        }],
        "voicing_plans": [{"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}],
        "bass_lines": [{"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6}],
        "groove_patterns": [{"id": "gp_01", "swing_level": 0.3, "syncopation_level": 0.4, "density": 0.6, "template_name": "house_basic"}],
        "melodic_complements": [{"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}],
        "scorecards": [{"candidate_id": "arr_01", "weighted_total": 0.8, "scores": {"loopability": 0.8}, "pareto_tags": []}],
        "on_progress": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_harvest_patterns_persists_one_entry_per_facet():
    state = _state_with_one_finalist()
    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)
    assert repo.upsert.await_count == 5
    assert len(result["harvested_pattern_ids"]) == 5
    state["on_progress"].assert_awaited_with("pattern_harvest", {"count": 5, "genre": "house"})


@pytest.mark.asyncio
async def test_harvest_patterns_continues_after_single_upsert_failure(caplog):
    """A transient Neo4j error on one facet must not abort the other 4."""
    state = _state_with_one_finalist()
    repo = AsyncMock()
    # First upsert raises; the remaining 4 succeed
    repo.upsert.side_effect = [RuntimeError("neo4j blip"), None, None, None, None]
    with caplog.at_level(logging.ERROR):
        result = await harvest_patterns(state, repo=repo)
    assert repo.upsert.await_count == 5
    assert len(result["harvested_pattern_ids"]) == 4  # one failure excluded
    assert any("harvest_patterns: failed to upsert" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_harvest_patterns_skips_when_no_final_selection():
    state = {"session_id": "sess_01", "genre": "house", "final_selection": {"selected_candidate_ids": []}}
    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)
    repo.upsert.assert_not_awaited()
    assert result["harvested_pattern_ids"] == []
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/engine/nodes/harvest_patterns.py`:

```python
"""LangGraph node: auto-harvest patterns from finalist arrangements."""
import logging
from typing import Any

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


async def harvest_patterns(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    final_selection = state.get("final_selection") or {}
    selected_ids: list[str] = final_selection.get("selected_candidate_ids") or []
    if not selected_ids:
        return {"harvested_pattern_ids": []}

    roles: dict[str, str] = final_selection.get("selection_roles") or {}
    genre = state.get("genre", "unknown")

    arrangements = _index_by_id(state.get("arrangement_candidates") or [])
    progressions = _index_by_id(state.get("progression_candidates") or [])
    voicing_plans = _index_by_id(state.get("voicing_plans") or [])
    bass_lines = _index_by_id(state.get("bass_lines") or [])
    grooves = _index_by_id(state.get("groove_patterns") or [])
    melodies = _index_by_id(state.get("melodic_complements") or [])
    scorecards_by_cand = {s.get("candidate_id"): s for s in (state.get("scorecards") or [])}

    harvested_ids: list[str] = []
    for arr_id in selected_ids:
        arrangement = arrangements.get(arr_id)
        if arrangement is None:
            continue
        progression = progressions.get(arrangement.get("progression_candidate_id"))
        if progression is None:
            continue
        scorecard = scorecards_by_cand.get(arr_id) or {"weighted_total": 0.0, "scores": {}, "pareto_tags": []}
        role = roles.get(arr_id, "unknown")

        entries = harvest_finalist(
            arrangement=arrangement,
            progression=progression,
            voicing_plan=voicing_plans.get(arrangement.get("voicing_plan_id")),
            bass_line=bass_lines.get(arrangement.get("bass_line_id")),
            groove=grooves.get(arrangement.get("groove_pattern_id")),
            melody=melodies.get(arrangement.get("melodic_complement_id")),
            scorecard=scorecard,
            genre=genre,
            role=role,
        )
        # Per-entry try/except: one failure doesn't block sibling facets or finalists.
        for entry in entries:
            try:
                await repo.upsert(entry)
                harvested_ids.append(entry.id)
            except Exception as exc:
                logger.error(
                    "harvest_patterns: failed to upsert entry %s (%s/%s): %s",
                    entry.id, entry.pattern_type, entry.source_candidate_id, exc,
                )

    on_progress = state.get("on_progress")
    if on_progress is not None:
        await on_progress("pattern_harvest", {"count": len(harvested_ids), "genre": genre})

    return {"harvested_pattern_ids": harvested_ids}
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/harvest_patterns.py backend/tests/engine/nodes/test_harvest_patterns.py
git commit -m "feat(m5d): harvest_patterns node with per-entry error isolation"
```

---

### Task 11: Wire `harvest_patterns` into the graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Create: `backend/tests/engine/test_graph.py` (if missing)

- [ ] **Step 1: Test**

```python
"""Graph-topology tests for M5d node wiring."""
from unittest.mock import MagicMock

from explorator.engine.graph import build_exploration_graph


def test_harvest_patterns_wired_between_persist_realization_and_persist_round():
    graph = build_exploration_graph(MagicMock(), MagicMock())
    nodes = set(graph.get_graph().nodes)
    assert "harvest_patterns" in nodes
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("persist_realization", "harvest_patterns") in edges
    assert ("harvest_patterns", "persist_round") in edges
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `graph.py`**

Add imports:
```python
from explorator.engine.nodes.harvest_patterns import harvest_patterns
from explorator.graph.pattern_library_repo import PatternLibraryRepo
```

Inside `build_exploration_graph`, after `graph.add_node("persist_realization", ...)`:
```python
    pattern_repo = PatternLibraryRepo(driver)
    graph.add_node("harvest_patterns", partial(harvest_patterns, repo=pattern_repo))
```

Replace `graph.add_edge("persist_realization", "persist_round")` with:
```python
    graph.add_edge("persist_realization", "harvest_patterns")
    graph.add_edge("harvest_patterns", "persist_round")
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/engine/test_graph.py
git commit -m "feat(m5d): wire harvest_patterns between persist_realization and persist_round"
```

---

## Phase 5 — Retrieval + warm-start loading

### Task 12: `fetch_warm_starts` function (no Protocol)

**Files:**
- Create: `backend/src/explorator/domain/memory/pattern_retrieval.py`
- Create: `backend/tests/domain/memory/test_pattern_retrieval.py`

- [ ] **Step 1: Test**

```python
"""Tests for fetch_warm_starts retrieval function."""
from unittest.mock import AsyncMock

import pytest

from explorator.domain.memory.pattern_retrieval import fetch_warm_starts


@pytest.mark.asyncio
async def test_fetch_warm_starts_delegates_to_repo():
    repo = AsyncMock()
    repo.query_for_warm_starts.return_value = {
        "progression": [{"id": "pl_1"}], "voicing": [{"id": "pl_2"}],
    }
    result = await fetch_warm_starts(repo=repo, genre="house", top_k_per_type=3)
    repo.query_for_warm_starts.assert_awaited_once_with(
        genre="house", top_k_per_type=3, tag_filters=None,
    )
    assert set(result.keys()) == {"progression", "voicing"}


@pytest.mark.asyncio
async def test_fetch_warm_starts_passes_tag_filters():
    repo = AsyncMock()
    repo.query_for_warm_starts.return_value = {}
    await fetch_warm_starts(repo=repo, genre="house", tag_filters=["role:safest"])
    repo.query_for_warm_starts.assert_awaited_once_with(
        genre="house", top_k_per_type=5, tag_filters=["role:safest"],
    )
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/domain/memory/pattern_retrieval.py`:

```python
"""Pattern retrieval — graph-backed warm-start lookup.

Kept as a single function for M5d. TODO(vector): swap the repo call for a
vector-backed retrieval when embeddings are populated.
"""
from typing import Any

from explorator.graph.pattern_library_repo import PatternLibraryRepo


async def fetch_warm_starts(
    *,
    repo: PatternLibraryRepo,
    genre: str,
    top_k_per_type: int = 5,
    tag_filters: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    return await repo.query_for_warm_starts(
        genre=genre, top_k_per_type=top_k_per_type, tag_filters=tag_filters,
    )
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/memory/pattern_retrieval.py backend/tests/domain/memory/test_pattern_retrieval.py
git commit -m "feat(m5d): fetch_warm_starts retrieval function with optional tag_filters"
```

---

### Task 13: `load_warm_starts` node with timeout

**Files:**
- Create: `backend/src/explorator/engine/nodes/load_warm_starts.py`
- Create: `backend/tests/engine/nodes/test_load_warm_starts.py`

- [ ] **Step 1: Test**

```python
"""Tests for load_warm_starts node."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.load_warm_starts import load_warm_starts, _TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_load_warm_starts_groups_by_pattern_type():
    state = {"warm_start_pattern_ids": ["pl_1", "pl_2", "pl_3"]}
    repo = AsyncMock()
    repo.get_by_id.side_effect = [
        {"id": "pl_1", "pattern_type": "progression", "abstracted_pattern": {}},
        {"id": "pl_2", "pattern_type": "voicing", "abstracted_pattern": {}},
        {"id": "pl_3", "pattern_type": "progression", "abstracted_pattern": {}},
    ]
    result = await load_warm_starts(state, repo=repo)
    assert sorted(result["warm_starts"].keys()) == ["progression", "voicing"]
    assert len(result["warm_starts"]["progression"]) == 2


@pytest.mark.asyncio
async def test_load_warm_starts_empty_when_no_ids():
    result = await load_warm_starts({}, repo=AsyncMock())
    assert result == {"warm_starts": {}}


@pytest.mark.asyncio
async def test_load_warm_starts_drops_missing_ids():
    state = {"warm_start_pattern_ids": ["pl_gone", "pl_ok"]}
    repo = AsyncMock()
    repo.get_by_id.side_effect = [None, {"id": "pl_ok", "pattern_type": "bass", "abstracted_pattern": {}}]
    result = await load_warm_starts(state, repo=repo)
    assert list(result["warm_starts"].keys()) == ["bass"]


@pytest.mark.asyncio
async def test_load_warm_starts_returns_empty_on_timeout(caplog):
    """A stuck Neo4j must not block generate — we log and continue with empty warm_starts."""
    state = {"warm_start_pattern_ids": ["pl_1"]}
    repo = AsyncMock()

    async def slow(_id: str) -> dict:
        await asyncio.sleep(_TIMEOUT_SECONDS + 1)
        return {"id": "pl_1", "pattern_type": "progression", "abstracted_pattern": {}}

    repo.get_by_id.side_effect = slow
    result = await load_warm_starts(state, repo=repo)
    assert result == {"warm_starts": {}}
    assert any("load_warm_starts: timeout" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/engine/nodes/load_warm_starts.py`:

```python
"""LangGraph node: hydrate warm-start pattern entries from Neo4j into state."""
import asyncio
import logging
from typing import Any

from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)

# Matches the pattern in load_memory.py — generation must not stall on retrieval.
_TIMEOUT_SECONDS = 5.0


async def _fetch_all(repo: PatternLibraryRepo, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for pid in ids:
        entry = await repo.get_by_id(pid)
        if entry is None:
            continue
        ptype = entry.get("pattern_type")
        if not ptype:
            continue
        grouped.setdefault(ptype, []).append(entry)
    return grouped


async def load_warm_starts(
    state: ExplorationState, *, repo: PatternLibraryRepo,
) -> dict[str, Any]:
    ids: list[str] = state.get("warm_start_pattern_ids") or []
    if not ids:
        return {"warm_starts": {}}
    try:
        grouped = await asyncio.wait_for(_fetch_all(repo, ids), timeout=_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.error("load_warm_starts: timeout after %ss, proceeding with empty warm_starts", _TIMEOUT_SECONDS)
        return {"warm_starts": {}}
    return {"warm_starts": grouped}
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/load_warm_starts.py backend/tests/engine/nodes/test_load_warm_starts.py
git commit -m "feat(m5d): load_warm_starts node with 5s timeout"
```

---

### Task 14: Wire `load_warm_starts` into the graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/tests/engine/test_graph.py`

- [ ] **Step 1: Append test**

```python
def test_load_warm_starts_wired_between_load_memory_and_generate():
    graph = build_exploration_graph(MagicMock(), MagicMock())
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("load_memory", "load_warm_starts") in edges
    assert ("load_warm_starts", "generate") in edges
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit**

Add import in `graph.py`:
```python
from explorator.engine.nodes.load_warm_starts import load_warm_starts
```

In `build_exploration_graph`, after the `pattern_repo` assignment:
```python
    graph.add_node("load_warm_starts", partial(load_warm_starts, repo=pattern_repo))
```

Replace `graph.add_edge("load_memory", "generate")` with:
```python
    graph.add_edge("load_memory", "load_warm_starts")
    graph.add_edge("load_warm_starts", "generate")
```

(If `pattern_repo` construction happens later in the function than needed here, hoist it above the edge additions.)

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/engine/test_graph.py
git commit -m "feat(m5d): wire load_warm_starts between load_memory and generate"
```

---

## Phase 6 — Generation-node warm-start seeding

The pattern across Tasks 15–19: read `state["warm_starts"].get(<type>)`; for progression (Task 15) construct a pre-built candidate and prepend; for voicing/bass/groove/melody inject the seed's *strategy* into the existing strategies/inputs list so the node's existing realizer produces real events. **Never return an artifact with empty event lists.**

### Task 15: Progression warm-start — prepend as candidate #1

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate.py`
- Create: `backend/tests/engine/nodes/test_generate_warm_start.py`

- [ ] **Step 1: Read current `generate.py`**

First, read `backend/src/explorator/engine/nodes/generate.py` and note:
- How `n_candidates` reaches the LLM prompt (inline interpolation vs. separate arg).
- The exact shape of the returned `progression_candidates` dict.
- Where `ULID`, `utc_now` are imported.

- [ ] **Step 2: Test (strong assertion)**

```python
"""Warm-start injection tests for generate node."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.generate import generate


@pytest.mark.asyncio
async def test_generate_prepends_warm_start_progression():
    gemini = AsyncMock()
    # LLM returns exactly (n_candidates - len(seeds)) candidates
    gemini.generate_json.return_value = {"progressions": [
        {"key_center": "C", "mode": "major", "chord_symbols": ["C", "G"], "phrase_length_bars": 2, "rationale": ""},
        {"key_center": "C", "mode": "major", "chord_symbols": ["F", "C"], "phrase_length_bars": 2, "rationale": ""},
    ]}

    state = {
        "session_id": "sess_01",
        "genre": "house",
        "genre_profile": {}, "harmonic_grammar": {},
        "creative_brief": {"genre": "house", "key_center": "C", "mode": "major", "phrase_length_bars": 2},
        "generation_mode": "balanced",
        "n_candidates": 3,
        "round_number": 1,
        "warm_starts": {"progression": [{
            "id": "pl_seed",
            "pattern_type": "progression",
            "abstracted_pattern": {
                "key_center": "C", "mode": "major",
                "chord_symbols": ["Cmaj7", "Am7", "Dm7", "G7"],
                "phrase_length_bars": 4,
                "roman_numerals": ["Imaj7", "vi7", "ii7", "V7"],
            },
        }]},
    }

    result = await generate(state, gemini=gemini)
    cands = result["progression_candidates"]

    # Strong: total equals requested count; first is warm-start; LLM called for n-1.
    assert len(cands) == 3
    assert cands[0]["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    assert cands[0]["metadata"]["warm_start_pattern_id"] == "pl_seed"
    assert cands[0]["generator_mode"] == "warm_start"

    # LLM was invoked exactly once with a prompt containing the reduced count.
    assert gemini.generate_json.await_count == 1
    prompt_str = " ".join(str(v) for v in gemini.generate_json.call_args.kwargs.values())
    assert " 2 " in prompt_str or "'n': 2" in prompt_str or '"n": 2' in prompt_str


@pytest.mark.asyncio
async def test_generate_unchanged_when_no_warm_start():
    gemini = AsyncMock()
    gemini.generate_json.return_value = {"progressions": [
        {"key_center": "C", "mode": "major", "chord_symbols": ["C", "G"], "phrase_length_bars": 2, "rationale": ""},
    ]}
    state = {
        "session_id": "sess_01", "genre": "house",
        "genre_profile": {}, "harmonic_grammar": {},
        "creative_brief": {"genre": "house", "key_center": "C", "mode": "major", "phrase_length_bars": 2},
        "generation_mode": "balanced", "n_candidates": 1, "round_number": 1,
    }
    result = await generate(state, gemini=gemini)
    assert len(result["progression_candidates"]) == 1
    assert result["progression_candidates"][0].get("generator_mode") != "warm_start"
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Modify `generate.py`**

Read-first rule: inspect `generate.py`, then edit. The shape of the change:

1. At the start of `generate(...)`:
   ```python
   warm_starts = state.get("warm_starts") or {}
   progression_seeds = warm_starts.get("progression") or []
   seed_candidates = [_build_seed_candidate(state, seed) for seed in progression_seeds]
   n_from_llm = max(0, state["n_candidates"] - len(seed_candidates))
   ```
2. Call the LLM with `n_from_llm` instead of `n_candidates`. If the prompt takes a numeric argument, pass `n_from_llm`; if it's embedded in the prompt string, build the prompt with `n_from_llm`. Match the file's existing shape.
3. If `n_from_llm == 0`, skip the LLM call entirely.
4. Return: `{"progression_candidates": seed_candidates + llm_candidates}`.

Define `_build_seed_candidate` at module level:

```python
def _build_seed_candidate(state: dict, seed: dict) -> dict:
    from ulid import ULID  # if not already imported
    from explorator.utils import utc_now
    now = utc_now()
    abstracted = seed.get("abstracted_pattern") or {}
    return {
        "id": f"prog_{ULID()}",
        "type": "progression_candidate",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "version": 1,
        "status": "active",
        "session_id": state["session_id"],
        "key_center": abstracted.get("key_center", state["creative_brief"].get("key_center", "C")),
        "mode": abstracted.get("mode", state["creative_brief"].get("mode", "major")),
        "chord_symbols": abstracted.get("chord_symbols") or [],
        "chord_events": [],  # evaluator rebuilds from chord_symbols; matches existing LLM path
        "phrase_length_bars": abstracted.get("phrase_length_bars", state["creative_brief"].get("phrase_length_bars", 4)),
        "generator_mode": "warm_start",
        "rationale": f"Seeded from pattern library entry {seed['id']}",
        "intent_tags": [],
        "metadata": {
            "warm_start_pattern_id": seed["id"],
            "roman_numerals": abstracted.get("roman_numerals", []),
        },
    }
```

(Adjust `chord_events`/other fields to match exactly what the existing LLM path produces — the test only asserts on `chord_symbols`, `metadata.warm_start_pattern_id`, and `generator_mode`, so any extras match existing shape.)

- [ ] **Step 5: Run** → all PASS (new test + any pre-existing `test_generate.py`).

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate.py backend/tests/engine/nodes/test_generate_warm_start.py
git commit -m "feat(m5d): prepend progression warm-start as candidate #1 in generate"
```

---

### Task 16: Voicing warm-start — seed a strategy, let realizer produce voicings

**Files:**
- Modify: `backend/src/explorator/engine/nodes/plan_voicings.py`
- Create: `backend/tests/engine/nodes/test_plan_voicings_warm_start.py`

- [ ] **Step 1: Read `plan_voicings.py`**

Note how the file builds strategies (LLM-produced list) and which generator turns a strategy into voicings. The warm-start injection happens at the strategy-list layer — we prepend a seeded strategy and let the existing `generator.generate_variants(strategy, progression, prefs)` produce voicings.

- [ ] **Step 2: Test**

```python
"""Warm-start injection for plan_voicings — strategy-level seeding."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.plan_voicings import plan_voicings


@pytest.mark.asyncio
async def test_voicing_warm_start_produces_realized_voicings_not_empty():
    """Critical invariant: a seeded voicing plan must have non-empty voicings list
    so downstream evaluation gates don't reject it as malformed."""
    gemini = AsyncMock()
    # LLM-produced strategies irrelevant for this test; return empty list
    gemini.generate_json.return_value = {"voicing_strategies": []}

    state = {
        "session_id": "sess_01",
        "genre": "house",
        "genre_profile": {},
        "top_progressions": [{
            "id": "prog_01", "key_center": "C", "mode": "major",
            "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4,
            "metadata": {},
        }],
        "warm_starts": {"voicing": [{
            "id": "pl_vseed", "pattern_type": "voicing",
            "abstracted_pattern": {"register_profile": "mid", "density": "sparse", "voice_count": 3},
        }]},
    }

    result = await plan_voicings(state, gemini=gemini)
    seeded = [vp for vp in result["voicing_plans"]
              if vp.get("metadata", {}).get("warm_start_pattern_id") == "pl_vseed"]
    assert len(seeded) == 1
    vp = seeded[0]
    assert vp["strategy"]["register_profile"] == "mid"
    assert vp["strategy"]["density"] == "sparse"
    assert vp["strategy"]["voice_count"] == 3
    # Invariant: realizer produced events (not an empty shell)
    assert len(vp["voicings"]) > 0
    assert vp["progression_candidate_id"] == "prog_01"
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Modify `plan_voicings.py`**

Read the file first. Structural edit:

1. After assembling the LLM-produced `strategies` list (typically `voicing_strategies` from the LLM response), prepend strategies derived from warm starts:
   ```python
   warm_starts = state.get("warm_starts") or {}
   for seed in warm_starts.get("voicing") or []:
       ap = seed.get("abstracted_pattern") or {}
       seeded_strategy = {
           "register_profile": ap.get("register_profile", "mid"),
           "density": ap.get("density", "medium"),
           "voice_count": int(ap.get("voice_count", 4)),
           # Marker consumed when building the VoicingPlan dict:
           "_warm_start_pattern_id": seed["id"],
       }
       strategies.insert(0, seeded_strategy)
   ```
2. In the loop that turns each strategy into a `VoicingPlan`, when a `_warm_start_pattern_id` marker is present, pop it and record in the plan's `metadata`:
   ```python
   warm_id = strategy.pop("_warm_start_pattern_id", None)
   metadata = {"warm_start_pattern_id": warm_id} if warm_id else {}
   ```
   Pass `metadata` through to `VoicingPlan(... metadata=metadata ...)`.
3. The existing realizer (e.g. `VoicingGenerator.generate_variants(strategy, progression, prefs)` or equivalent) is invoked unchanged, so `vp["voicings"]` is populated by the deterministic realizer — the empty-events trap is avoided.

- [ ] **Step 5: Run** → PASS (including any pre-existing `test_plan_voicings.py`).

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/nodes/plan_voicings.py backend/tests/engine/nodes/test_plan_voicings_warm_start.py
git commit -m "feat(m5d): seed voicing strategy; realizer produces non-empty voicings"
```

---

### Task 17: Bass warm-start — strategy-level seed

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_bass.py`
- Create: `backend/tests/engine/nodes/test_generate_bass_warm_start.py`

- [ ] **Step 1: Test**

```python
"""Bass warm-start: seed (mode, rhythmic_density) and ensure realizer emits notes."""
import pytest

from explorator.engine.nodes.generate_bass import generate_bass


@pytest.mark.asyncio
async def test_bass_warm_start_produces_realized_notes_not_empty():
    state = {
        "session_id": "sess_01",
        "top_progressions": [{
            "id": "prog_01", "chord_symbols": ["C", "F", "G", "C"],
            "key_center": "C", "mode": "major", "phrase_length_bars": 4,
        }],
        "voicing_plans": [{
            "id": "vp_01", "progression_candidate_id": "prog_01",
            "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4},
            "voicings": [{"beat": 1, "pitches": [60, 64, 67]}],  # minimally realized
        }],
        "groove_patterns": [],  # not required if node tolerates its absence
        "warm_starts": {"bass": [{
            "id": "pl_bseed", "pattern_type": "bass",
            "abstracted_pattern": {"mode": "walking", "rhythmic_density": 0.65},
        }]},
    }
    result = await generate_bass(state)
    seeded = [bl for bl in result["bass_lines"]
              if bl.get("metadata", {}).get("warm_start_pattern_id") == "pl_bseed"]
    assert len(seeded) == 1
    assert seeded[0]["mode"] == "walking"
    assert seeded[0]["rhythmic_density"] == pytest.approx(0.65)
    # Invariant: realizer produced notes
    assert len(seeded[0]["notes"]) > 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Modify `generate_bass.py`**

Read-first. Structural edit:

1. Find the per-voicing-plan loop that produces a `BassLine`.
2. After the normal loop, iterate warm-start seeds and call the same deterministic bass-line generator with the seed's `mode` and `rhythmic_density` — ensuring `notes` gets populated. Attach `{"warm_start_pattern_id": seed["id"]}` to the plan's `metadata`.

Pseudocode:
```python
warm_starts = state.get("warm_starts") or {}
for seed in warm_starts.get("bass") or []:
    ap = seed.get("abstracted_pattern") or {}
    for vp in state.get("voicing_plans") or []:
        bl = _build_bass_line_from_strategy(
            voicing_plan=vp,
            progression=_find_progression(vp["progression_candidate_id"], state),
            mode=ap.get("mode", "root"),
            rhythmic_density=float(ap.get("rhythmic_density", 0.5)),
        )
        bl["metadata"] = {"warm_start_pattern_id": seed["id"]}
        bass_lines.append(bl)
```

Use whatever helper `generate_bass.py` already has for producing a bass line from a strategy. If no such helper exists but the inline deterministic logic is clear, extract it into `_build_bass_line_from_strategy(...)` first (refactor) before adding the warm-start loop — keep the refactor in the same commit if it's small.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_bass.py backend/tests/engine/nodes/test_generate_bass_warm_start.py
git commit -m "feat(m5d): seed bass (mode, rhythmic_density); realizer emits notes"
```

---

### Task 18: Groove warm-start — strategy-level seed

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_groove.py`
- Create: `backend/tests/engine/nodes/test_generate_groove_warm_start.py`

- [ ] **Step 1: Test**

```python
import pytest

from explorator.engine.nodes.generate_groove import generate_groove


@pytest.mark.asyncio
async def test_groove_warm_start_produces_realized_events_not_empty():
    state = {
        "session_id": "sess_01",
        "top_progressions": [{"id": "prog_01", "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4}],
        "warm_starts": {"groove": [{
            "id": "pl_gseed", "pattern_type": "groove",
            "abstracted_pattern": {
                "swing_level": 0.3, "syncopation_level": 0.5,
                "density": 0.7, "template_name": "house_basic",
            },
        }]},
    }
    result = await generate_groove(state)
    seeded = [g for g in result["groove_patterns"]
              if g.get("metadata", {}).get("warm_start_pattern_id") == "pl_gseed"]
    assert len(seeded) == 1
    g = seeded[0]
    assert g["swing_level"] == pytest.approx(0.3)
    assert g["syncopation_level"] == pytest.approx(0.5)
    # Invariant: realizer produced events
    assert len(g["events"]) > 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Modify `generate_groove.py`**

Read first. The groove node currently picks or constructs a `GroovePattern` per progression. For each warm-start seed, invoke the same deterministic template-expansion with the seed's `swing_level`, `syncopation_level`, `density`, `template_name` — producing a real `events` list. Attach `metadata.warm_start_pattern_id`.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_groove.py backend/tests/engine/nodes/test_generate_groove_warm_start.py
git commit -m "feat(m5d): seed groove strategy; template produces non-empty events"
```

---

### Task 19: Melody warm-start — strategy-level seed

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_melody.py`
- Create: `backend/tests/engine/nodes/test_generate_melody_warm_start.py`

- [ ] **Step 1: Test**

```python
from unittest.mock import AsyncMock
import pytest

from explorator.engine.nodes.generate_melody import generate_melody


@pytest.mark.asyncio
async def test_melody_warm_start_seeds_strategy_and_realizer_produces_notes():
    gemini = AsyncMock()
    # Existing Gemini-strategy path returns nothing; only the warm-start seed flows through.
    gemini.generate_json.return_value = {"melody_strategies": []}

    state = {
        "session_id": "sess_01",
        "arrangement_candidates": [{
            "id": "arr_01", "progression_candidate_id": "prog_01",
            "voicing_plan_id": "vp_01", "bass_line_id": "bl_01", "groove_pattern_id": "gp_01",
        }],
        "top_progressions": [{"id": "prog_01", "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4, "key_center": "C", "mode": "major"}],
        "groove_patterns": [{"id": "gp_01", "events": [], "swing_level": 0.0, "syncopation_level": 0.0, "density": 0.5}],
        "warm_starts": {"melody": [{
            "id": "pl_mseed", "pattern_type": "melody",
            "abstracted_pattern": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5},
        }]},
    }
    result = await generate_melody(state, gemini=gemini)
    seeded = [m for m in result["melodic_complements"]
              if m.get("metadata", {}).get("warm_start_pattern_id") == "pl_mseed"]
    assert len(seeded) == 1
    m = seeded[0]
    assert m["strategy"]["contour_type"] == "arch"
    assert m["strategy"]["range_semitones"] == 14
    # Invariant: realizer produced notes
    assert len(m["notes"]) > 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Modify `generate_melody.py`**

Read-first. The melody node is two-phase (Gemini strategy → deterministic realization). Inject seed strategies at the strategy-list layer before the realization phase. For each warm-start seed × arrangement, build a strategy dict from `contour_type`, `range_semitones`, `rhythmic_density`, then let the existing realizer produce notes. Attach `metadata.warm_start_pattern_id`.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_melody.py backend/tests/engine/nodes/test_generate_melody_warm_start.py
git commit -m "feat(m5d): seed melody strategy; realizer produces non-empty notes"
```

---

## Phase 7 — API & session integration

### Task 20: Dependency provider + shared test fixtures

**Files:**
- Modify: `backend/src/explorator/api/deps.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add provider to `deps.py`**

```python
from explorator.graph.pattern_library_repo import PatternLibraryRepo


def get_pattern_library_repo(
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> PatternLibraryRepo:
    return PatternLibraryRepo(driver)
```

- [ ] **Step 2: Add fixtures to root `conftest.py`**

Read existing fixtures first (`rg "^def " backend/tests/conftest.py`). Append:

```python
import pytest
from datetime import datetime, UTC

from explorator.models.memory import PatternLibraryEntry


@pytest.fixture
async def seed_patterns(neo4j_driver):
    """Upsert 3 patterns via PatternLibraryRepo and return their dicts.

    Two house patterns (progression role:safest, voicing role:most_experimental)
    and one techno pattern (progression role:safest).
    """
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    repo = PatternLibraryRepo(neo4j_driver)
    now = datetime.now(UTC)

    entries = [
        PatternLibraryEntry(
            id="pl_seed_a", type="pattern_library_entry",
            created_at=now, updated_at=now, status="active", metadata={},
            pattern_type="progression", genre="house",
            tags=["role:safest", "loopability_high", "cadence:authentic", "complexity:mid"],
            source_candidate_id="arr_seed_a",
            abstracted_pattern={"chord_symbols": ["C", "F", "G", "C"], "key_center": "C", "mode": "major", "phrase_length_bars": 4, "roman_numerals": ["I", "IV", "V", "I"]},
            success_metrics={"weighted_total": 0.85, "loopability": 0.9},
        ),
        PatternLibraryEntry(
            id="pl_seed_b", type="pattern_library_entry",
            created_at=now, updated_at=now, status="active", metadata={},
            pattern_type="voicing", genre="house",
            tags=["role:most_experimental", "register:high", "density:sparse", "voices:3"],
            source_candidate_id="arr_seed_b",
            abstracted_pattern={"register_profile": "high", "density": "sparse", "voice_count": 3},
            success_metrics={"weighted_total": 0.75},
        ),
        PatternLibraryEntry(
            id="pl_seed_c", type="pattern_library_entry",
            created_at=now, updated_at=now, status="active", metadata={},
            pattern_type="progression", genre="techno",
            tags=["role:safest"],
            source_candidate_id="arr_seed_c",
            abstracted_pattern={"chord_symbols": ["Am", "F", "C", "G"], "key_center": "A", "mode": "minor", "phrase_length_bars": 4},
            success_metrics={"weighted_total": 0.7},
        ),
    ]
    for entry in entries:
        await repo.upsert(entry)
    yield [e.model_dump() for e in entries]
    # Cleanup
    for entry in entries:
        await repo.delete_by_id(entry.id)


@pytest.fixture
async def seeded_house_session(client):
    """Create a session with genre='house' and return its creation response."""
    resp = await client.post(
        "/v1/sessions",
        json={"mode": "balanced", "prompt": "moody house", "genre": "house"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def completed_session(client, neo4j_driver, seeded_house_session):
    """Create a house session with a synthetic final_selection + arrangement graph.

    Inserts the minimum node set harvest_finalists needs: an ArrangementCandidate
    with all 5 facet pointers, a ProgressionCandidate, a VoicingPlan, a BassLine,
    a GroovePattern, a MelodicComplement, an AggregateScorecard, and stamps
    final_selection onto the Session node as JSON (matching persist_realization's format).
    """
    sid = seeded_house_session["session_id"]
    async with neo4j_driver.session() as neo:
        await neo.run("""
        MATCH (s:Session {id: $sid})
        SET s.final_selection = $fs,
            s.genre = 'house'
        """, sid=sid, fs='{"selected_candidate_ids": ["arr_cs_01"], "selection_roles": {"arr_cs_01": "safest"}}')

        await neo.run("""
        CREATE (p:ProgressionCandidate {
            id: 'prog_cs_01', type: 'progression_candidate',
            status: 'selected', session_id: $sid,
            key_center: 'C', mode: 'major',
            chord_symbols: '["C", "F", "G", "C"]',
            phrase_length_bars: 4,
            metadata: '{"roman_numerals": ["I", "IV", "V", "I"]}'
        })
        CREATE (v:VoicingPlan {
            id: 'vp_cs_01', type: 'voicing_plan', status: 'active',
            progression_candidate_id: 'prog_cs_01',
            strategy: '{"register_profile": "mid", "density": "medium", "voice_count": 4}',
            voicings: '[{"beat": 1, "pitches": [60, 64, 67]}]'
        })
        CREATE (b:BassLine {
            id: 'bl_cs_01', type: 'bass_line', status: 'active',
            mode: 'root', rhythmic_density: 0.5,
            notes: '[{"beat": 1, "pitch": 36}]'
        })
        CREATE (g:GroovePattern {
            id: 'gp_cs_01', type: 'groove_pattern', status: 'active',
            swing_level: 0.0, syncopation_level: 0.0, density: 0.5,
            template_name: 'house_basic', events: '[]'
        })
        CREATE (m:MelodicComplement {
            id: 'mc_cs_01', type: 'melodic_complement', status: 'active',
            strategy: '{"contour_type": "arch", "range_semitones": 12, "rhythmic_density": 0.5}',
            notes: '[]'
        })
        CREATE (a:ArrangementCandidate {
            id: 'arr_cs_01', type: 'arrangement_candidate',
            status: 'selected', session_id: $sid,
            progression_candidate_id: 'prog_cs_01',
            voicing_plan_id: 'vp_cs_01', bass_line_id: 'bl_cs_01',
            groove_pattern_id: 'gp_cs_01', melodic_complement_id: 'mc_cs_01',
            metadata: '{"role": "safest"}'
        })
        CREATE (sc:AggregateScorecard {
            id: 'sc_cs_01', type: 'aggregate_scorecard', status: 'active',
            candidate_id: 'arr_cs_01', weighted_total: 0.8,
            scores: '{"loopability": 0.85, "cadence_quality": 0.8}',
            pareto_tags: '[]'
        })
        CREATE (a)-[:HAS_SCORECARD]->(sc)
        """, sid=sid)
    yield seeded_house_session
    # Cleanup
    async with neo4j_driver.session() as neo:
        await neo.run("""
        MATCH (n) WHERE n.id IN [
            'prog_cs_01','vp_cs_01','bl_cs_01','gp_cs_01','mc_cs_01','arr_cs_01','sc_cs_01'
        ] DETACH DELETE n
        """)
```

- [ ] **Step 3: Smoke-run fixtures**

`cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v` — already passing — ensures no conftest regression.

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/api/deps.py backend/tests/conftest.py
git commit -m "feat(m5d): PatternLibraryRepo DI provider + shared test fixtures"
```

---

### Task 21: `GET /v1/patterns` with `from_entry` helper

**Files:**
- Create: `backend/src/explorator/api/routes/patterns.py`
- Create: `backend/tests/api/test_patterns_router.py`
- Modify: `backend/src/explorator/api/app.py`

- [ ] **Step 1: Tests**

```python
"""Integration tests for /v1/patterns router."""
import pytest


@pytest.mark.asyncio
async def test_list_patterns_empty(client):
    resp = await client.get("/v1/patterns")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_list_patterns_filter_by_genre(client, seed_patterns):
    resp = await client.get("/v1/patterns?genre=house")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(i["genre"] == "house" for i in items)


@pytest.mark.asyncio
async def test_list_patterns_filter_by_type_and_tags(client, seed_patterns):
    resp = await client.get("/v1/patterns?genre=house&pattern_type=progression&tags=role:safest")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["pattern_type"] == "progression" and "role:safest" in i["tags"] for i in items)
    assert len(items) >= 1
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/api/routes/patterns.py`:

```python
"""Pattern library HTTP API (M5d)."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from explorator.api.deps import get_pattern_library_repo
from explorator.graph.pattern_library_repo import PatternLibraryRepo

router = APIRouter(tags=["patterns"])


class PatternItem(BaseModel):
    id: str
    pattern_type: str
    genre: str
    tags: list[str]
    source_candidate_id: str
    abstracted_pattern: dict[str, Any]
    success_metrics: dict[str, float]
    notes: str = ""

    @classmethod
    def from_entry(cls, e: dict[str, Any]) -> "PatternItem":
        return cls(
            id=e["id"], pattern_type=e["pattern_type"], genre=e["genre"],
            tags=e.get("tags") or [], source_candidate_id=e["source_candidate_id"],
            abstracted_pattern=e.get("abstracted_pattern") or {},
            success_metrics=e.get("success_metrics") or {},
            notes=e.get("notes") or "",
        )


class PatternListResponse(BaseModel):
    items: list[PatternItem]


@router.get("/patterns")
async def list_patterns(
    genre: str | None = None,
    pattern_type: str | None = None,
    tags: str | None = Query(None, description="Comma-separated tag filters"),
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    entries = await repo.list_all(genre=genre, pattern_type=pattern_type, tags=tag_list)
    return PatternListResponse(items=[PatternItem.from_entry(e) for e in entries])
```

Register in `app.py` (order: after `sessions`, before catch-alls):

```python
from explorator.api.routes import patterns
...
app.include_router(patterns.router, prefix="/v1")
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/src/explorator/api/app.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): GET /v1/patterns with filters, shared from_entry helper"
```

---

### Task 22: `GET /v1/patterns/{id}` + `DELETE /v1/patterns/{id}`

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Tests**

```python
@pytest.mark.asyncio
async def test_get_pattern_by_id(client, seed_patterns):
    pid = seed_patterns[0]["id"]
    resp = await client.get(f"/v1/patterns/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.asyncio
async def test_get_pattern_404(client):
    assert (await client.get("/v1/patterns/pl_missing")).status_code == 404


@pytest.mark.asyncio
async def test_delete_pattern(client, seed_patterns):
    pid = seed_patterns[0]["id"]
    assert (await client.delete(f"/v1/patterns/{pid}")).status_code == 204
    assert (await client.get(f"/v1/patterns/{pid}")).status_code == 404
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Append endpoints**

```python
@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternItem:
    entry = await repo.get_by_id(pattern_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return PatternItem.from_entry(entry)


@router.delete("/patterns/{pattern_id}", status_code=204)
async def delete_pattern(
    pattern_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> None:
    entry = await repo.get_by_id(pattern_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    await repo.delete_by_id(pattern_id)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): GET and DELETE /v1/patterns/{id}"
```

---

### Task 23: Genre field on session + `parse_intent` reconciliation

**Files:**
- Modify: `backend/src/explorator/api/routes/sessions.py`
- Modify: `backend/src/explorator/engine/nodes/parse_intent.py`
- Create: `backend/tests/api/test_sessions_router.py` (extend if exists)
- Create: `backend/tests/engine/nodes/test_parse_intent_warm_start.py`

- [ ] **Step 1: Tests**

`backend/tests/api/test_sessions_router.py`:
```python
import pytest


@pytest.mark.asyncio
async def test_create_session_accepts_genre_stored_as_top_level_property(client, neo4j_driver):
    resp = await client.post(
        "/v1/sessions",
        json={"mode": "balanced", "prompt": "moody house", "genre": "house"},
    )
    assert resp.status_code == 201
    sid = resp.json()["session_id"]
    async with neo4j_driver.session() as neo:
        result = await neo.run("MATCH (s:Session {id: $sid}) RETURN s.genre AS genre", sid=sid)
        record = await result.single()
    assert record["genre"] == "house"

    detail = await client.get(f"/v1/sessions/{sid}")
    assert detail.json().get("genre") == "house"


@pytest.mark.asyncio
async def test_create_session_genre_optional(client):
    resp = await client.post("/v1/sessions", json={"mode": "balanced", "prompt": "anything"})
    assert resp.status_code == 201
    assert resp.json().get("genre") in (None, "")
```

`backend/tests/engine/nodes/test_parse_intent_warm_start.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from explorator.engine.nodes.parse_intent import parse_intent


@pytest.mark.asyncio
async def test_parse_intent_prefers_preset_genre_over_llm_inference(monkeypatch):
    """If state['genre'] is already set (from user Dashboard pick), respect it."""
    fake_brief = MagicMock()
    fake_brief.genre = "chamber_pop"  # what LLM would infer from prompt
    fake_brief.model_dump.return_value = {"genre": "chamber_pop"}

    from explorator.domain.intent import parser as _parser
    monkeypatch.setattr(_parser, "IntentParser", lambda _g: MagicMock(parse=AsyncMock(return_value=fake_brief)))

    state = {"session_id": "sess_01", "prompt": "a sad ballad", "genre": "house"}
    result = await parse_intent(state, gemini=MagicMock())
    assert result["genre"] == "house"
    # creative_brief.genre also reconciled so downstream load_genre uses the right profile
    assert result["creative_brief"]["genre"] == "house"


@pytest.mark.asyncio
async def test_parse_intent_falls_back_to_llm_when_no_preset(monkeypatch):
    fake_brief = MagicMock()
    fake_brief.genre = "techno"
    fake_brief.model_dump.return_value = {"genre": "techno"}

    from explorator.domain.intent import parser as _parser
    monkeypatch.setattr(_parser, "IntentParser", lambda _g: MagicMock(parse=AsyncMock(return_value=fake_brief)))

    state = {"session_id": "sess_01", "prompt": "dark techno"}  # no preset genre
    result = await parse_intent(state, gemini=MagicMock())
    assert result["genre"] == "techno"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `sessions.py`**

```python
class CreateSessionRequest(BaseModel):
    mode: str = "full_exploration"
    prompt: str
    genre: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    status: str
    mode: str
    created_at: str
    prompt: str
    genre: str | None = None
    warm_start_pattern_ids: list[str] = []
```

In `create_session`, build the Session node with a top-level `genre` property (not in metadata):

```python
session = Session(
    id=session_id, type="session", status="active",
    mode=request.mode, created_at=now, updated_at=now,
    metadata={"prompt": request.prompt},
)
await repo.create(session)

if request.genre:
    # Stamp genre as a first-class property for downstream reads.
    async with driver.session() as neo:
        await neo.run(
            "MATCH (s:Session {id: $id}) SET s.genre = $genre",
            id=session_id, genre=request.genre,
        )
```

(Inject `driver: AsyncDriver = Depends(get_neo4j_driver)` into `create_session`.)

In `get_session` and `list_sessions`, read `session.get("genre")` (flat property) and `session.get("warm_start_pattern_ids", [])` (flat array) and include in response.

- [ ] **Step 4: Edit `parse_intent.py`**

```python
async def parse_intent(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "parse_intent"})

    parser = IntentParser(gemini)
    brief = await parser.parse(state["prompt"], state["session_id"])

    # If the user explicitly picked a genre on Dashboard, it wins over LLM inference.
    preset_genre = state.get("genre")
    if preset_genre:
        brief_dict = brief.model_dump(mode="json")
        brief_dict["genre"] = preset_genre
        genre = preset_genre
    else:
        brief_dict = brief.model_dump(mode="json")
        genre = brief.genre

    result = {"creative_brief": brief_dict, "genre": genre}

    if callback:
        await callback("node_completed", {"node": "parse_intent", "genre": genre})
    return result
```

- [ ] **Step 5: Run** → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/api/routes/sessions.py backend/src/explorator/engine/nodes/parse_intent.py backend/tests/api/test_sessions_router.py backend/tests/engine/nodes/test_parse_intent_warm_start.py
git commit -m "feat(m5d): genre on session + parse_intent reconciliation"
```

---

### Task 24: `GET /v1/sessions/{id}/warm-starts`

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Tests**

```python
@pytest.mark.asyncio
async def test_warm_starts_grouped_by_pattern_type(client, seeded_house_session, seed_patterns):
    resp = await client.get(f"/v1/sessions/{seeded_house_session['session_id']}/warm-starts")
    assert resp.status_code == 200
    body = resp.json()
    assert "progression" in body["suggestions"]
    assert all(p["genre"] == "house" for p in body["suggestions"]["progression"])


@pytest.mark.asyncio
async def test_warm_starts_empty_when_session_has_no_genre(client):
    sr = await client.post("/v1/sessions", json={"mode": "balanced", "prompt": "plain"})
    sid = sr.json()["session_id"]
    resp = await client.get(f"/v1/sessions/{sid}/warm-starts")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == {}
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Append to `patterns.py`:

```python
from neo4j import AsyncDriver
from explorator.api.deps import get_neo4j_driver, get_session_repo
from explorator.domain.memory.pattern_retrieval import fetch_warm_starts
from explorator.graph.session_repo import SessionRepository


class WarmStartSuggestions(BaseModel):
    suggestions: dict[str, list[PatternItem]]


@router.get("/sessions/{session_id}/warm-starts")
async def get_warm_start_suggestions(
    session_id: str,
    top_k_per_type: int = 5,
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
    pattern_repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> WarmStartSuggestions:
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    genre = session.get("genre")
    if not genre:
        return WarmStartSuggestions(suggestions={})
    grouped = await fetch_warm_starts(repo=pattern_repo, genre=genre, top_k_per_type=top_k_per_type)
    return WarmStartSuggestions(suggestions={
        ptype: [PatternItem.from_entry(e) for e in entries]
        for ptype, entries in grouped.items()
    })
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): GET /v1/sessions/{id}/warm-starts"
```

---

### Task 25: `POST /v1/sessions/{id}/warm-starts` — flat array property

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Tests**

```python
@pytest.mark.asyncio
async def test_set_warm_starts_stores_flat_array_property(client, seeded_house_session, seed_patterns, neo4j_driver):
    sid = seeded_house_session["session_id"]
    ids = [seed_patterns[0]["id"]]
    resp = await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": ids})
    assert resp.status_code == 200
    assert resp.json() == {"pattern_ids": ids}

    # Verify it's a native Neo4j string array, not embedded in metadata JSON
    async with neo4j_driver.session() as neo:
        result = await neo.run(
            "MATCH (s:Session {id: $sid}) RETURN s.warm_start_pattern_ids AS ids",
            sid=sid,
        )
        record = await result.single()
    assert record["ids"] == ids

    detail = await client.get(f"/v1/sessions/{sid}")
    assert detail.json().get("warm_start_pattern_ids") == ids


@pytest.mark.asyncio
async def test_set_warm_starts_rejects_unknown_pattern_ids(client, seeded_house_session):
    sid = seeded_house_session["session_id"]
    resp = await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": ["pl_ghost"]})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_set_warm_starts_concurrent_does_not_clobber_metadata(client, seeded_house_session, seed_patterns, neo4j_driver):
    """Flat array write must not touch the metadata JSON blob."""
    sid = seeded_house_session["session_id"]
    await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": [seed_patterns[0]["id"]]})
    async with neo4j_driver.session() as neo:
        result = await neo.run(
            "MATCH (s:Session {id: $sid}) RETURN s.metadata AS meta",
            sid=sid,
        )
        record = await result.single()
    # Original metadata (with prompt) must be unchanged.
    assert "prompt" in record["meta"]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Append to `patterns.py`:

```python
class SetWarmStartsRequest(BaseModel):
    pattern_ids: list[str]


class SetWarmStartsResponse(BaseModel):
    pattern_ids: list[str]


@router.post("/sessions/{session_id}/warm-starts")
async def set_warm_starts(
    session_id: str,
    request: SetWarmStartsRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
    pattern_repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> SetWarmStartsResponse:
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for pid in request.pattern_ids:
        if await pattern_repo.get_by_id(pid) is None:
            raise HTTPException(status_code=400, detail=f"Pattern not found: {pid}")

    # Flat native Neo4j string array — no JSON metadata round-trip, no race.
    async with driver.session() as neo_session:
        await neo_session.run(
            "MATCH (s:Session {id: $sid}) SET s.warm_start_pattern_ids = $ids",
            sid=session_id, ids=request.pattern_ids,
        )
    return SetWarmStartsResponse(pattern_ids=request.pattern_ids)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): POST /v1/sessions/{id}/warm-starts using flat Neo4j array"
```

---

### Task 26: `rounds.py` reads flat properties into `initial_state`

**Files:**
- Modify: `backend/src/explorator/api/routes/rounds.py`
- Create: `backend/tests/api/test_rounds_router.py` (or extend)

- [ ] **Step 1: Test**

```python
import asyncio
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_trigger_round_passes_warm_start_ids_and_genre(client, monkeypatch, seeded_house_session, seed_patterns, neo4j_driver):
    captured: list[dict] = []

    class _FakeGraph:
        async def ainvoke(self, state, _cfg):
            captured.append(state)
            return state

    monkeypatch.setattr(
        "explorator.api.routes.rounds.build_exploration_graph",
        lambda *_a, **_kw: _FakeGraph(),
    )

    sid = seeded_house_session["session_id"]
    await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": [seed_patterns[0]["id"]]})

    async with client.stream("POST", f"/v1/sessions/{sid}/rounds", json={"generation_mode": "balanced"}) as r:
        async for _ in r.aiter_lines():
            break
    await asyncio.sleep(0.2)

    assert captured, "graph was not invoked"
    state = captured[0]
    assert state.get("warm_start_pattern_ids") == [seed_patterns[0]["id"]]
    assert state.get("genre") == "house"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `rounds.py`**

In `trigger_round`, alongside the existing session lookup:

```python
# Flat-property reads — no JSON parse
genre = session.get("genre", "")
warm_start_pattern_ids = list(session.get("warm_start_pattern_ids") or [])
```

Add to `initial_state`:
```python
"genre": genre,
"warm_start_pattern_ids": warm_start_pattern_ids,
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/rounds.py backend/tests/api/test_rounds_router.py
git commit -m "feat(m5d): rounds reads genre + warm_start_pattern_ids from Session flat properties"
```

---

### Task 27: `POST /v1/sessions/{id}/finalists/harvest` — real repos only

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

The repos confirmed to exist (from `ls backend/src/explorator/graph/`):
- `ArrangementCandidateRepo` (`arrangement_candidate_repo.py`)
- `BassLineRepo` (`bass_line_repo.py`)
- `GroovePatternRepo` (`groove_pattern_repo.py`)
- `VoicingPlanRepo` (`voicing_plan_repo.py`)
- `MelodicComplementRepo` (`melodic_complement_repo.py`)
- `ProgressionCandidateRepo` — lives in `repository.py` (not a dedicated file)

Scorecards and final_selection are **not** in dedicated repo files — read directly via Cypher:
- Scorecard: `(AggregateScorecard)` node with `candidate_id` property.
- `final_selection`: JSON string property on the `Session` node (written by `persist_realization.py`).

- [ ] **Step 1: Test**

```python
@pytest.mark.asyncio
async def test_harvest_finalists_endpoint_persists_patterns(client, completed_session):
    sid = completed_session["session_id"]
    resp = await client.post(f"/v1/sessions/{sid}/finalists/harvest")
    assert resp.status_code == 200
    count_1 = resp.json()["harvested_count"]
    assert count_1 == 5  # arr_cs_01 has all 5 facets

    # Idempotent: second call updates but doesn't duplicate.
    resp2 = await client.post(f"/v1/sessions/{sid}/finalists/harvest")
    assert resp2.status_code == 200
    assert resp2.json()["harvested_count"] == 5

    # Verify only 5 library rows for this source_candidate_id.
    list_resp = await client.get("/v1/patterns?genre=house")
    from_this = [p for p in list_resp.json()["items"] if p["source_candidate_id"] == "arr_cs_01"]
    assert len(from_this) == 5


@pytest.mark.asyncio
async def test_harvest_finalists_404_on_unknown_session(client):
    assert (await client.post("/v1/sessions/sess_missing/finalists/harvest")).status_code == 404


@pytest.mark.asyncio
async def test_harvest_finalists_empty_when_no_final_selection(client, seeded_house_session):
    sid = seeded_house_session["session_id"]
    resp = await client.post(f"/v1/sessions/{sid}/finalists/harvest")
    assert resp.status_code == 200
    assert resp.json()["harvested_count"] == 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Append to `patterns.py`:

```python
import json as _json

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.bass_line_repo import BassLineRepo
from explorator.graph.groove_pattern_repo import GroovePatternRepo
from explorator.graph.melodic_complement_repo import MelodicComplementRepo
from explorator.graph.repository import ProgressionCandidateRepo, _neo4j_deserialize
from explorator.graph.voicing_plan_repo import VoicingPlanRepo


class HarvestFinalistsResponse(BaseModel):
    harvested_count: int
    pattern_ids: list[str]


async def _load_final_selection(driver: AsyncDriver, session_id: str) -> dict[str, Any] | None:
    """Read final_selection JSON string from the Session node (written by persist_realization)."""
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (s:Session {id: $sid}) RETURN s.final_selection AS fs",
            sid=session_id,
        )
        record = await result.single()
    if record is None:
        return None
    raw = record["fs"]
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return _json.loads(raw)
    except (TypeError, ValueError):
        return None


async def _load_scorecard(driver: AsyncDriver, candidate_id: str) -> dict[str, Any] | None:
    async with driver.session() as neo:
        result = await neo.run(
            "MATCH (sc:AggregateScorecard {candidate_id: $cid}) RETURN sc",
            cid=candidate_id,
        )
        record = await result.single()
    if record is None:
        return None
    return _neo4j_deserialize(dict(record["sc"]))


@router.post("/sessions/{session_id}/finalists/harvest")
async def harvest_finalists_endpoint(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
    pattern_repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> HarvestFinalistsResponse:
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    genre = session.get("genre") or "unknown"

    final = await _load_final_selection(driver, session_id)
    if final is None or not final.get("selected_candidate_ids"):
        return HarvestFinalistsResponse(harvested_count=0, pattern_ids=[])

    roles: dict[str, str] = final.get("selection_roles") or {}
    arr_repo = ArrangementCandidateRepo(driver)
    prog_repo = ProgressionCandidateRepo(driver)
    vp_repo = VoicingPlanRepo(driver)
    bl_repo = BassLineRepo(driver)
    gp_repo = GroovePatternRepo(driver)
    mc_repo = MelodicComplementRepo(driver)

    harvested: list[str] = []
    for arr_id in final["selected_candidate_ids"]:
        arrangement = await arr_repo.get_by_id(arr_id)
        if arrangement is None:
            continue
        progression = await prog_repo.get_by_id(arrangement.get("progression_candidate_id"))
        if progression is None:
            continue
        vp = await vp_repo.get_by_id(arrangement["voicing_plan_id"]) if arrangement.get("voicing_plan_id") else None
        bl = await bl_repo.get_by_id(arrangement["bass_line_id"]) if arrangement.get("bass_line_id") else None
        gp = await gp_repo.get_by_id(arrangement["groove_pattern_id"]) if arrangement.get("groove_pattern_id") else None
        mc = await mc_repo.get_by_id(arrangement["melodic_complement_id"]) if arrangement.get("melodic_complement_id") else None
        scorecard = await _load_scorecard(driver, arr_id) or {"weighted_total": 0.0, "scores": {}, "pareto_tags": []}
        role = roles.get(arr_id, "unknown")

        entries = harvest_finalist(
            arrangement=arrangement, progression=progression,
            voicing_plan=vp, bass_line=bl, groove=gp, melody=mc,
            scorecard=scorecard, genre=genre, role=role,
        )
        # Idempotent at the DB layer via natural-key MERGE.
        for entry in entries:
            try:
                await pattern_repo.upsert(entry)
                harvested.append(entry.id)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error(
                    "harvest_finalists: failed to upsert %s: %s", entry.id, exc,
                )
    return HarvestFinalistsResponse(harvested_count=len(harvested), pattern_ids=harvested)
```

**Note:** `BaseRepository.get_by_id(...)` returns a deserialized dict for the requested label — trust the existing pattern. If any of these repos don't expose `get_by_id`, add a thin wrapper to the repo file in the same commit (it's a standard method on `BaseRepository`).

- [ ] **Step 4: Run** → PASS (all 3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): POST /sessions/{id}/finalists/harvest using verified repos"
```

---

## Phase 8 — Frontend

### Task 28: Install Sonner, mount Toaster, add `/patterns` route stub

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/toastWrapper.ts`
- Create: `frontend/src/components/PatternLibraryBrowser.tsx` (stub)
- Create: `frontend/src/constants/patternTypes.ts`

- [ ] **Step 1: Install**

`cd frontend && npm install sonner`

- [ ] **Step 2: Create the wrapper + constants**

`frontend/src/components/toastWrapper.ts`:
```ts
import { toast } from 'sonner';
export const toastSuccess = (msg: string) => toast.success(msg);
export const toastError = (msg: string) => toast.error(msg);
export const toastInfo = (msg: string) => toast(msg);
```

`frontend/src/constants/patternTypes.ts`:
```ts
// Mirror of backend/src/explorator/constants.py PATTERN_TYPES.
export const PATTERN_TYPES = ['progression', 'voicing', 'bass', 'groove', 'melody'] as const;
export type PatternType = typeof PATTERN_TYPES[number];
```

`frontend/src/components/PatternLibraryBrowser.tsx` (stub for route):
```tsx
export default function PatternLibraryBrowser() {
  return <div>Pattern Library (implemented in Task 32)</div>;
}
```

- [ ] **Step 3: Mount `Toaster` + route**

`frontend/src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';
import GenreManagement from './components/GenreManagement';
import PatternLibraryBrowser from './components/PatternLibraryBrowser';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/genres" element={<GenreManagement />} />
          <Route path="/patterns" element={<PatternLibraryBrowser />} />
          <Route path="/session/:id" element={<SessionWorkspace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 4: Type-check**

`cd frontend && npx tsc --noEmit` → no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/App.tsx frontend/src/components/toastWrapper.ts frontend/src/components/PatternLibraryBrowser.tsx frontend/src/constants/patternTypes.ts
git commit -m "feat(m5d): Sonner toaster, /patterns route, PATTERN_TYPES constant"
```

---

### Task 29: Pattern API client in `services/api.ts`

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Read `api.ts` for `API_BASE` and existing call patterns**

- [ ] **Step 2: Append**

```ts
import type { PatternType } from '../constants/patternTypes';

export interface PatternItem {
  id: string;
  pattern_type: PatternType;
  genre: string;
  tags: string[];
  source_candidate_id: string;
  abstracted_pattern: Record<string, unknown>;
  success_metrics: Record<string, number>;
  notes: string;
}

export interface PatternFilters {
  genre?: string;
  pattern_type?: PatternType;
  tags?: string[];
}

export async function listPatterns(filters: PatternFilters = {}): Promise<PatternItem[]> {
  const params = new URLSearchParams();
  if (filters.genre) params.set('genre', filters.genre);
  if (filters.pattern_type) params.set('pattern_type', filters.pattern_type);
  if (filters.tags?.length) params.set('tags', filters.tags.join(','));
  const url = `${API_BASE}/v1/patterns${params.toString() ? '?' + params : ''}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`listPatterns failed: ${resp.status}`);
  return (await resp.json()).items;
}

export async function getPattern(id: string): Promise<PatternItem> {
  const resp = await fetch(`${API_BASE}/v1/patterns/${id}`);
  if (!resp.ok) throw new Error(`getPattern failed: ${resp.status}`);
  return resp.json();
}

export async function deletePattern(id: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/v1/patterns/${id}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error(`deletePattern failed: ${resp.status}`);
}

export async function getWarmStartSuggestions(sessionId: string): Promise<Record<string, PatternItem[]>> {
  const resp = await fetch(`${API_BASE}/v1/sessions/${sessionId}/warm-starts`);
  if (!resp.ok) throw new Error(`getWarmStartSuggestions failed: ${resp.status}`);
  return (await resp.json()).suggestions;
}

export async function setWarmStarts(sessionId: string, patternIds: string[]): Promise<string[]> {
  const resp = await fetch(`${API_BASE}/v1/sessions/${sessionId}/warm-starts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pattern_ids: patternIds }),
  });
  if (!resp.ok) throw new Error(`setWarmStarts failed: ${resp.status}`);
  return (await resp.json()).pattern_ids;
}

export async function harvestFinalists(sessionId: string): Promise<{ harvested_count: number; pattern_ids: string[] }> {
  const resp = await fetch(`${API_BASE}/v1/sessions/${sessionId}/finalists/harvest`, { method: 'POST' });
  if (!resp.ok) throw new Error(`harvestFinalists failed: ${resp.status}`);
  return resp.json();
}
```

- [ ] **Step 3: Type-check → commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(m5d): pattern API client functions + shared PatternItem type"
```

---

### Task 30: `patternLibraryStore`

**Files:**
- Create: `frontend/src/stores/patternLibraryStore.ts`
- Create: `frontend/src/stores/__tests__/patternLibraryStore.test.ts`

- [ ] **Step 1: Test**

```ts
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { usePatternLibraryStore } from '../patternLibraryStore';
import * as api from '../../services/api';

vi.mock('../../services/api');

describe('patternLibraryStore', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
    vi.clearAllMocks();
  });

  it('fetches patterns by filter', async () => {
    const mock: api.PatternItem[] = [{ id: 'pl_1', pattern_type: 'progression', genre: 'house', tags: [], source_candidate_id: 'arr_1', abstracted_pattern: {}, success_metrics: {}, notes: '' }];
    vi.mocked(api.listPatterns).mockResolvedValue(mock);
    await usePatternLibraryStore.getState().fetchPatterns({ genre: 'house' });
    expect(usePatternLibraryStore.getState().patterns).toEqual(mock);
    expect(api.listPatterns).toHaveBeenCalledWith({ genre: 'house' });
  });

  it('toggles selections', () => {
    const s = usePatternLibraryStore.getState();
    s.toggleSelection('pl_1');
    s.toggleSelection('pl_2');
    expect(usePatternLibraryStore.getState().selectedPatternIds).toEqual(['pl_1', 'pl_2']);
    s.toggleSelection('pl_1');
    expect(usePatternLibraryStore.getState().selectedPatternIds).toEqual(['pl_2']);
  });

  it('removePattern calls API then updates list', async () => {
    vi.mocked(api.deletePattern).mockResolvedValue(undefined);
    vi.mocked(api.listPatterns).mockResolvedValue([
      { id: 'pl_1', pattern_type: 'progression', genre: 'house', tags: [], source_candidate_id: 'arr_1', abstracted_pattern: {}, success_metrics: {}, notes: '' },
      { id: 'pl_2', pattern_type: 'voicing', genre: 'house', tags: [], source_candidate_id: 'arr_2', abstracted_pattern: {}, success_metrics: {}, notes: '' },
    ]);
    await usePatternLibraryStore.getState().fetchPatterns({ genre: 'house' });
    await usePatternLibraryStore.getState().removePattern('pl_1');
    expect(api.deletePattern).toHaveBeenCalledWith('pl_1');
    expect(usePatternLibraryStore.getState().patterns.map(p => p.id)).toEqual(['pl_2']);
  });
});
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```ts
import { create } from 'zustand';
import { listPatterns, deletePattern, type PatternItem, type PatternFilters } from '../services/api';

interface State {
  patterns: PatternItem[];
  loading: boolean;
  error: string | null;
  selectedPatternIds: string[];
  activeFilter: PatternFilters;

  fetchPatterns: (filters: PatternFilters) => Promise<void>;
  toggleSelection: (id: string) => void;
  clearSelection: () => void;
  removePattern: (id: string) => Promise<void>;
  reset: () => void;
}

export const usePatternLibraryStore = create<State>((set, get) => ({
  patterns: [],
  loading: false,
  error: null,
  selectedPatternIds: [],
  activeFilter: {},

  fetchPatterns: async (filters) => {
    set({ loading: true, error: null, activeFilter: filters });
    try {
      const items = await listPatterns(filters);
      set({ patterns: items, loading: false });
    } catch (e) {
      set({ loading: false, error: (e as Error).message });
    }
  },

  toggleSelection: (id) => set((s) => ({
    selectedPatternIds: s.selectedPatternIds.includes(id)
      ? s.selectedPatternIds.filter((x) => x !== id)
      : [...s.selectedPatternIds, id],
  })),

  clearSelection: () => set({ selectedPatternIds: [] }),

  removePattern: async (id) => {
    await deletePattern(id);
    set({ patterns: get().patterns.filter((p) => p.id !== id) });
  },

  reset: () => set({ patterns: [], loading: false, error: null, selectedPatternIds: [], activeFilter: {} }),
}));
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/patternLibraryStore.ts frontend/src/stores/__tests__/patternLibraryStore.test.ts
git commit -m "feat(m5d): patternLibraryStore"
```

---

### Task 31: `WarmStartPanel`

**Files:**
- Create: `frontend/src/components/WarmStartPanel.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useEffect, useState } from 'react';
import { listPatterns, type PatternItem } from '../services/api';
import { PATTERN_TYPES, type PatternType } from '../constants/patternTypes';

interface Props {
  genre: string;
  selectedIds: string[];
  onToggle: (id: string) => void;
  onStartFresh: () => void;
}

export default function WarmStartPanel({ genre, selectedIds, onToggle, onStartFresh }: Props) {
  const [patterns, setPatterns] = useState<PatternItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!genre) { setPatterns([]); return; }
    setLoading(true);
    listPatterns({ genre })
      .then(setPatterns)
      .catch(() => setPatterns([]))
      .finally(() => setLoading(false));
  }, [genre]);

  if (loading) return <div data-testid="warm-start-loading">Loading patterns…</div>;
  if (!patterns || patterns.length === 0) return null;

  const grouped = PATTERN_TYPES
    .map((ptype) => ({ ptype, items: patterns.filter((p) => p.pattern_type === ptype) }))
    .filter((g) => g.items.length > 0);

  return (
    <section data-testid="warm-start-panel" className="warm-start-panel">
      <h3>Warm start from {genre} patterns</h3>
      <p className="subtitle">Pick patterns to seed your session, or start fresh.</p>
      {grouped.map(({ ptype, items }) => (
        <div key={ptype} className="warm-start-group">
          <h4>{ptype}</h4>
          <ul>
            {items.map((p) => (
              <li key={p.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(p.id)}
                    onChange={() => onToggle(p.id)}
                    data-testid={`warm-start-toggle-${p.id}`}
                  />
                  <span className="tags">{p.tags.join(', ')}</span>
                  <span className="score">{(p.success_metrics.weighted_total ?? 0).toFixed(2)}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <button type="button" onClick={onStartFresh} data-testid="start-fresh-btn">
        Start fresh (skip warm start)
      </button>
    </section>
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
git add frontend/src/components/WarmStartPanel.tsx
git commit -m "feat(m5d): WarmStartPanel component"
```

---

### Task 32: `PatternLibraryBrowser` with provenance link

**Files:**
- Modify: `frontend/src/components/PatternLibraryBrowser.tsx`

- [ ] **Step 1: Replace stub**

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePatternLibraryStore } from '../stores/patternLibraryStore';
import { toastSuccess, toastError } from './toastWrapper';
import { PATTERN_TYPES } from '../constants/patternTypes';

export default function PatternLibraryBrowser() {
  const navigate = useNavigate();
  const { patterns, loading, fetchPatterns, removePattern } = usePatternLibraryStore();
  const [genreFilter, setGenreFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  useEffect(() => {
    fetchPatterns({
      genre: genreFilter || undefined,
      pattern_type: (typeFilter || undefined) as any,
    });
  }, [genreFilter, typeFilter, fetchPatterns]);

  return (
    <div className="pattern-library" data-testid="pattern-library-browser">
      <header>
        <button onClick={() => navigate('/')}>← Back</button>
        <h1>Pattern Library</h1>
      </header>
      <div className="filters">
        <input
          placeholder="Filter by genre"
          value={genreFilter}
          onChange={(e) => setGenreFilter(e.target.value)}
          data-testid="filter-genre"
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} data-testid="filter-type">
          <option value="">All types</option>
          {PATTERN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      {loading && <p>Loading…</p>}
      {!loading && patterns.length === 0 && (
        <p data-testid="empty-library">No patterns yet. They'll appear here after a session reaches finalist selection.</p>
      )}
      <ul>
        {patterns.map((p) => (
          <li key={p.id} data-testid={`pattern-row-${p.id}`}>
            <span className="type">{p.pattern_type}</span>
            <span className="genre">{p.genre}</span>
            <span className="tags">{p.tags.join(', ')}</span>
            <span className="score">{(p.success_metrics.weighted_total ?? 0).toFixed(2)}</span>
            {/* Provenance link — spec §5.6. Source is an ArrangementCandidate ID;
                the frontend resolves to its session via /v1/sessions/by-arrangement/... */}
            <a
              href={`/patterns/source/${p.source_candidate_id}`}
              data-testid={`provenance-${p.id}`}
              title="View source arrangement"
            >
              source: {p.source_candidate_id}
            </a>
            <button
              type="button"
              data-testid={`delete-pattern-${p.id}`}
              onClick={async () => {
                try {
                  await removePattern(p.id);
                  toastSuccess('Pattern deleted');
                } catch (e) {
                  toastError((e as Error).message);
                }
              }}
            >Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Type-check + smoke-check**

`cd frontend && npx tsc --noEmit && npm run dev` — visit `http://0.0.0.0:5173/patterns`, confirm empty state or list.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PatternLibraryBrowser.tsx
git commit -m "feat(m5d): PatternLibraryBrowser with filters, delete, provenance link"
```

---

### Task 33: Wire `WarmStartPanel` into Dashboard

**Files:**
- Modify: `frontend/src/views/Dashboard.tsx`

- [ ] **Step 1: Read existing Dashboard.tsx** — note how `createSession` is called and what it passes.

- [ ] **Step 2: Add genre selector + panel + `/patterns` nav link**

Integrate per the file's existing shape. Minimum changes:

```tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import WarmStartPanel from '../components/WarmStartPanel';
import { createSession, setWarmStarts } from '../services/api';
import { toastInfo } from '../components/toastWrapper';
...
const [genre, setGenre] = useState('');
const [selectedPatternIds, setSelectedPatternIds] = useState<string[]>([]);
const navigate = useNavigate();
...
const handleSubmit = async () => {
  const { session_id } = await createSession({ prompt, genre, mode });
  if (selectedPatternIds.length > 0) {
    await setWarmStarts(session_id, selectedPatternIds);
    toastInfo(`${selectedPatternIds.length} warm-start${selectedPatternIds.length === 1 ? '' : 's'} applied.`);
  }
  navigate(`/session/${session_id}`);
};
...
<Link to="/patterns" data-testid="dashboard-patterns-link">Pattern Library</Link>
<select value={genre} onChange={(e) => setGenre(e.target.value)} data-testid="dashboard-genre">
  <option value="">Pick a genre…</option>
  {availableGenres.map((g) => <option key={g} value={g}>{g}</option>)}
</select>
{genre && (
  <WarmStartPanel
    genre={genre}
    selectedIds={selectedPatternIds}
    onToggle={(id) => setSelectedPatternIds((ids) =>
      ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id]
    )}
    onStartFresh={() => setSelectedPatternIds([])}
  />
)}
```

If the existing `createSession(...)` call signature doesn't take `genre`, update it (and `frontend/src/services/api.ts`'s `createSession`) to pass `genre` through in the POST body.

- [ ] **Step 3: Smoke-check + commit**

```bash
git add frontend/src/views/Dashboard.tsx frontend/src/services/api.ts
git commit -m "feat(m5d): Dashboard wires genre selector + WarmStartPanel + /patterns nav"
```

---

### Task 34: `Save to library` button + auto-harvest SSE toast

**Files:**
- Modify: `frontend/src/components/FinalistPanel.tsx`
- Modify: `frontend/src/components/SessionWorkspace.tsx`

- [ ] **Step 1: Add `Save finalists to library` button to FinalistPanel**

Read current FinalistPanel. Add:

```tsx
import { harvestFinalists } from '../services/api';
import { toastSuccess, toastError } from './toastWrapper';
...
const handleSaveToLibrary = async () => {
  try {
    const { harvested_count } = await harvestFinalists(sessionId);
    toastSuccess(
      harvested_count === 0
        ? 'Finalists already saved to library'
        : `${harvested_count} patterns saved to library`
    );
  } catch (err) {
    toastError((err as Error).message);
  }
};
...
<button
  type="button"
  onClick={handleSaveToLibrary}
  data-testid="save-to-library-btn"
>
  Save finalists to library
</button>
```

- [ ] **Step 2: Add SSE `pattern_harvest` handler in SessionWorkspace**

Read the file's SSE dispatch (look for a `switch` on event type or `if (event === ...)`). Add:

```ts
import { toastSuccess } from './toastWrapper';
...
// In the SSE event handler:
if (eventType === 'pattern_harvest') {
  const { count, genre } = JSON.parse(data);
  if (count > 0) {
    toastSuccess(`${count} ${genre} pattern${count === 1 ? '' : 's'} saved to library`);
  }
}
```

Match the file's existing event-dispatch shape exactly.

- [ ] **Step 3: Smoke-check + commit**

```bash
git add frontend/src/components/FinalistPanel.tsx frontend/src/components/SessionWorkspace.tsx
git commit -m "feat(m5d): Save-to-library button + auto-harvest SSE toast"
```

---

## Phase 9 — E2E tests

### Task 35: E2E harness + auto-harvest test

**Files:**
- Create: `e2e/tests/warm-starts.spec.ts`
- Create or extend: `e2e/fixtures/session.ts`

- [ ] **Step 1: Fixture**

`e2e/fixtures/session.ts`:
```ts
import { Page, expect } from '@playwright/test';

export async function runFullSession(page: Page, { genre, prompt }: { genre: string; prompt: string }) {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', genre);
  await page.fill('[data-testid=dashboard-prompt]', prompt);
  await page.click('[data-testid=dashboard-submit]');
  await page.waitForURL(/\/session\/sess_/);
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 180_000 });
}
```

(Adjust test-ids to match what `Dashboard.tsx` actually renders — confirm during Task 33 implementation.)

- [ ] **Step 2: Test**

```ts
import { test, expect } from '@playwright/test';
import { runFullSession } from '../fixtures/session';

test.describe('M5d — Retrieval-Assisted Warm Starts', () => {
  test('patterns harvested automatically after finalist selection', async ({ page, request }) => {
    const before = await (await request.get('/v1/patterns?genre=house')).json();
    await runFullSession(page, { genre: 'house', prompt: 'bouncy house groove' });
    const after = await (await request.get('/v1/patterns?genre=house')).json();
    expect(after.items.length).toBeGreaterThan(before.items.length);
  });
});
```

- [ ] **Step 3: Run + commit**

```bash
cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium
git add e2e/tests/warm-starts.spec.ts e2e/fixtures/session.ts
git commit -m "test(m5d): e2e auto-harvest after finalist selection"
```

---

### Task 36: E2E — browser shows harvested pattern

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Append**

```ts
test('harvested pattern appears in library browser with role tag', async ({ page }) => {
  await runFullSession(page, { genre: 'house', prompt: 'warm-start source run' });
  await page.goto('/patterns');
  await expect(page.locator('[data-testid=pattern-library-browser]')).toBeVisible();
  await page.fill('[data-testid=filter-genre]', 'house');
  const rows = page.locator('[data-testid^=pattern-row-]');
  await expect(rows).not.toHaveCount(0);
  await expect(rows.filter({ hasText: 'progression' }).first()).toContainText(/role:(safest|best_loop|most_experimental)/);
});
```

- [ ] **Step 2: Run + commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e verify library browser shows harvested pattern"
```

---

### Task 37: E2E — warm-start panel appears + seeds round 1

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Append**

```ts
test('warm-start panel appears when patterns exist for chosen genre', async ({ page }) => {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('[data-testid^=warm-start-toggle-]')).not.toHaveCount(0);
});


test('warm-start seeds round-1 generation with pre-built candidate', async ({ page, request }) => {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible();
  const firstToggle = page.locator('[data-testid^=warm-start-toggle-]').first();
  const tid = await firstToggle.getAttribute('data-testid');
  const patternId = tid!.replace('warm-start-toggle-', '');
  await firstToggle.check();
  await page.fill('[data-testid=dashboard-prompt]', 'seeded session');
  await page.click('[data-testid=dashboard-submit]');
  await page.waitForURL(/\/session\/sess_/);
  const sessionId = page.url().split('/').pop()!;
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 180_000 });

  const resp = await (await request.get(`/v1/sessions/${sessionId}/candidates`)).json();
  const seeded = resp.items.some((c: { metadata?: { warm_start_pattern_id?: string } }) =>
    c.metadata?.warm_start_pattern_id === patternId
  );
  expect(seeded).toBe(true);
});
```

- [ ] **Step 2: Run + commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e warm-start panel + round-1 seeding"
```

---

### Task 38: E2E — "Start fresh" + deletion

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Append both tests**

```ts
test('start-fresh clears selection and skips warm start', async ({ page, request }) => {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible();
  await page.locator('[data-testid^=warm-start-toggle-]').first().check();
  await page.click('[data-testid=start-fresh-btn]');
  expect(await page.locator('[data-testid^=warm-start-toggle-]:checked').count()).toBe(0);

  await page.fill('[data-testid=dashboard-prompt]', 'fresh');
  await page.click('[data-testid=dashboard-submit]');
  await page.waitForURL(/\/session\/sess_/);
  const sessionId = page.url().split('/').pop()!;
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 180_000 });
  const resp = await (await request.get(`/v1/sessions/${sessionId}/candidates`)).json();
  expect(resp.items.every((c: { metadata?: { warm_start_pattern_id?: string } }) =>
    !c.metadata?.warm_start_pattern_id
  )).toBe(true);
});


test('pattern can be deleted from library', async ({ page, request }) => {
  const list = await (await request.get('/v1/patterns?genre=house')).json();
  expect(list.items.length).toBeGreaterThan(0);
  const victim = list.items[0];

  await page.goto('/patterns');
  await page.fill('[data-testid=filter-genre]', 'house');
  const row = page.locator(`[data-testid=pattern-row-${victim.id}]`);
  await expect(row).toBeVisible();
  await row.locator(`[data-testid=delete-pattern-${victim.id}]`).click();
  await expect(row).toHaveCount(0, { timeout: 5_000 });

  expect((await request.get(`/v1/patterns/${victim.id}`)).status()).toBe(404);
});
```

- [ ] **Step 2: Run + commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e start-fresh + pattern deletion"
```

---

## Phase 10 — Integration polish

### Task 39: Full regression + manual smoke

- [ ] **Step 1: Backend suite**

`cd backend && uv run pytest -v` → all PASS; no regression from M5a/b/c. Expect count ≥ (prior M5b/c baseline) + M5d additions.

- [ ] **Step 2: Frontend suite**

`cd frontend && npx vitest run && npx tsc --noEmit && npm run build` → all PASS, clean tsc, successful build.

- [ ] **Step 3: E2E suite**

`cd e2e && npx playwright test --project=chromium` → all PASS, including 5 new warm-starts tests.

- [ ] **Step 4: Manual smoke**

Start backend (`cd backend && uv run uvicorn explorator.api.app:app --host 0.0.0.0 --port 8000`) and frontend (`cd frontend && npm run dev`), then:

1. Open http://0.0.0.0:5173/
2. Create a new **house** session (no patterns yet) — verify no WarmStartPanel appears.
3. Wait for session completion — verify toast: "N house patterns saved to library".
4. Click "Save finalists to library" — verify toast: "Finalists already saved to library" (idempotent — no new row count).
5. Navigate to /patterns — verify the entries show with correct tags (role:*, loopability_*, cadence:*, complexity:*).
6. Return to / and create a **second** house session — verify WarmStartPanel now appears with harvested patterns.
7. Select one progression warm-start + one groove warm-start; submit.
8. Verify in the running session: at least one progression candidate has `warm_start_pattern_id` in metadata (inspect via /v1/sessions/{id}/candidates) and at least one groove pattern produces non-empty events.
9. Delete one pattern from /patterns — verify UI removal and 404 on direct GET.

- [ ] **Step 5: Commit any smoke-driven tweaks**

```bash
git add -u
git commit -m "chore(m5d): manual-smoke polish"
```

(Or skip if clean.)

---

## Self-Review Checklist

**Spec coverage:**
- §5.2 Pattern Harvesting — Tasks 6–11 ✓ (progression tags now include cadence + complexity)
- §5.3 Retrieval — Tasks 5, 12, 13 ✓ (tag_filters plumbed through)
- §5.4 Backend API — Tasks 21, 22, 24, 25, 27 ✓
- §5.5 Warm Start Integration — Tasks 15–19 ✓ (strategy-level seeding for 4 of 5 types ensures realized events)
- §5.6 Frontend — Tasks 28–34 ✓ (provenance link included)
- §5.7 E2E Tests — Tasks 35–38 ✓ (5 tests; matches "5-6 new")

**Critique fixes addressed:**
- Auto-harvest idempotence → Task 5 uses MERGE on natural key; no in-Python dedupe needed.
- Empty-event-list trap → Tasks 16–19 seed at strategy level; test invariants assert `len(voicings) > 0`, `len(notes) > 0`, `len(events) > 0`.
- `services/` directory → relocated to `domain/memory/` (Task 6).
- Phantom repos in manual harvest → Task 27 uses verified repos only; scorecard/final_selection read via direct Cypher.
- Session metadata concurrency → Task 25 uses flat Neo4j array property; Task 23 stamps genre as top-level property too.
- Genre reconciliation → Task 23 updates `parse_intent` to prefer preset `state["genre"]`.
- Legacy stub rows → Task 3 adds migration script.
- `_build_entry` helper → Task 6 introduces; Tasks 7–8 consume.
- `PatternItem.from_entry` → Task 21 introduces; Tasks 22, 24 consume.
- `RetrievalStrategy` Protocol → replaced with plain `fetch_warm_starts` function (Task 12) + TODO comment on embedding field (Task 1).
- Tighter test assertions → Task 15 asserts exact n-1 count in LLM call; Tasks 16–19 assert realizer-produced non-empty event lists.
- `asyncio.sleep` flakiness → kept in rounds-router test (Task 26) as the only source; SSE teardown makes this hard to avoid without mocking further.
- `datetime.now()` → all tests use `datetime.now(UTC)` or delegate via fixtures calling repo/harvesting (which use `utc_now()`).
- `json` import → Task 27 imports `json` at top (`import json as _json`).
- Cadence + complexity tags → Task 6 emits `cadence:{authentic|plagal|half|deceptive|other}` and `complexity:{low|mid|high}`.
- Tag filters on retrieval → Task 5 repo accepts `tag_filters`; Task 12 passes them through.
- PATTERN_TYPES constant → Task 4 (backend) + Task 28 (frontend mirror).

**Type consistency:**
- `PatternLibraryEntry` shape matches across model, repo, harvesting, API response (`PatternItem`), and frontend `PatternItem` interface.
- Repo methods `upsert / get_by_id / list_all / delete_by_id / query_for_warm_starts` consistent across definition, tests, and callers.
- `harvest_finalist` kwargs consistent between unit tests (Task 8), auto-node (Task 10), and manual endpoint (Task 27).
- `warm_start_pattern_id` metadata key identical across all 5 generation nodes and their tests.

**Execution handoff:**
- 39 tasks total. Phases 1–5 (data + repo + harvesting + retrieval + load node) are fully deterministic and safe to execute in sequence.
- Phases 6 (Tasks 15–19) require careful read-before-edit on each generation node; the "realizer produces non-empty events" invariant is the load-bearing check — do not let these tests be softened.
- Phase 7 (API) is straightforward once the repo and fixtures are in place.
- Phase 8 (frontend) depends on backend being stable; recommend backend CI pass before starting frontend tasks.
- Phase 9 (E2E) requires full-stack running.

Risk areas for the executing agent:
- Task 15 (progression warm-start) — the LLM count assertion is now stricter; if `generate.py` composes its prompt in an unusual way, the assertion may need a one-line adjustment to match the real call shape, but the invariant (LLM asked for n-1) must hold.
- Tasks 16–19 — require finding each node's deterministic realizer. If a node currently bakes the realization into a big function, extract a small `_build_from_strategy(...)` helper first (in the same task), then use it for both the LLM-strategy and warm-start-strategy paths.
- Task 27 — `BaseRepository.get_by_id` shape assumption is load-bearing; verify during implementation and add a thin wrapper if the method doesn't exist on a specific repo.
