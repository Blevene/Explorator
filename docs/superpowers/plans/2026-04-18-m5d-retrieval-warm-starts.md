# M5d — Retrieval-Assisted Warm Starts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harvest reusable patterns (progression, voicing, bass, groove, melody) from finalist candidates into a Neo4j-backed library, then offer those patterns as optional warm starts when the user creates a new session for the same genre.

**Architecture:** A new `PatternLibraryRepo` stores `PatternLibraryEntry` nodes in Neo4j. A `harvest_patterns` LangGraph node auto-runs when the exploration loop terminates (before `persist_round`), abstracting each finalist into typed patterns with auto-generated tags. A `load_warm_starts` node runs after `parse_intent` and populates state with selected patterns. Generation nodes (`generate`, `plan_voicings`, `generate_bass`, `generate_groove`, `generate_melody`) consume warm-start data as pre-seeded candidates/strategies (option (a) — the pattern becomes a slot in round 1). A new `patterns` FastAPI router exposes list/get/delete plus per-session warm-start suggestions. Frontend adds a `patternLibraryStore`, `WarmStartPanel` (pre-generation), `PatternLibraryBrowser` (library view), a "Save to library" button in `FinalistPanel`, and Sonner toasts for auto-harvest feedback.

**Tech Stack:** Python 3.12, FastAPI, Neo4j (Cypher), LangGraph, Pydantic; React + TypeScript, Zustand, React Router, Sonner; Playwright for E2E.

---

## Design decisions locked before tasks begin

1. **Auto-harvest trigger** — `harvest_patterns` runs between `persist_realization` and `persist_round` (graph edge change). This is the final step after the exploration loop terminates. The finalists it reads are the `final_selection.selected_candidate_ids` assigned `safest` / `best_loop` / `most_experimental` roles by `rank_and_select`.

2. **Manual re-save** — `FinalistPanel` gets an explicit "Save to library" button that calls a dedicated `POST /v1/sessions/{id}/finalists/harvest` endpoint. The endpoint is idempotent (upsert by `source_candidate_id + pattern_type`), so clicking it after auto-harvest is a no-op or refresh.

3. **Warm-start injection mode** — option (a) everywhere: patterns bypass LLM generation for one slot in round 1. For progressions, the pattern's chord sequence becomes candidate #1 (LLM generates N−1 others). For voicing/bass/groove/melody, the pattern's abstracted parameters become a pre-built plan/strategy for the matching progression family, and the LLM-driven strategy generators produce the rest.

4. **Genre source** — `POST /v1/sessions` gains an optional `genre` field. Frontend `Dashboard` requires explicit genre selection before showing the warm-start panel. `GET /v1/sessions/{id}/warm-starts` reads genre from session metadata.

5. **Toast** — Sonner (~3KB gzipped, one dependency). Mounted once in `App.tsx`. Used for the "N patterns saved to library" notification after auto-harvest and for manual-save confirmations.

6. **RetrievalQuery entity** — the Pydantic model is a request DTO, not persisted. It exists so future VectorRetrieval can take the same input. `RetrievalResult` is also unused in M5d (results are returned inline).

7. **Embedding field** — added as `embedding: list[float] | None = None`, always stored as `null` in M5d. Present so swapping to `VectorRetrieval` later requires no schema migration.

---

## File Structure

### Backend — create

| Path | Responsibility |
|------|---------------|
| `backend/src/explorator/graph/pattern_library_repo.py` | Neo4j CRUD for `PatternLibraryEntry` (upsert, get, list-with-filters, delete, query-by-genre-tags) |
| `backend/src/explorator/services/pattern_harvesting.py` | Abstract finalist candidates into typed patterns; generate tags |
| `backend/src/explorator/services/pattern_retrieval.py` | `GraphRetrieval` strategy class wrapping Cypher queries; strategy interface for future `VectorRetrieval` |
| `backend/src/explorator/engine/nodes/harvest_patterns.py` | LangGraph node: reads `final_selection` from state, calls harvesting service, persists via repo, emits SSE event |
| `backend/src/explorator/engine/nodes/load_warm_starts.py` | LangGraph node: reads `warm_start_pattern_ids` from state, loads entries from repo, populates `state['warm_starts']` keyed by pattern_type |
| `backend/src/explorator/api/routes/patterns.py` | FastAPI router: GET/DELETE /v1/patterns; GET/POST /v1/sessions/{id}/warm-starts; POST /v1/sessions/{id}/finalists/harvest |
| `backend/tests/services/test_pattern_harvesting.py` | Unit tests for pattern abstraction + tag generation |
| `backend/tests/services/test_pattern_retrieval.py` | Unit tests for retrieval strategy |
| `backend/tests/graph/test_pattern_library_repo.py` | Repo unit tests against test Neo4j |
| `backend/tests/engine/nodes/test_harvest_patterns.py` | Node unit tests |
| `backend/tests/engine/nodes/test_load_warm_starts.py` | Node unit tests |
| `backend/tests/api/test_patterns_router.py` | Router integration tests |

### Backend — modify

| Path | Change |
|------|--------|
| `backend/src/explorator/models/memory.py` | Add `embedding: list[float] \| None = None` to `PatternLibraryEntry`; make `source_candidate_id: str` required (remove `\| None = None`) |
| `backend/src/explorator/graph/schema.py` | Add indexes for `PatternLibraryEntry` on genre, pattern_type, and a composite genre+pattern_type |
| `backend/src/explorator/api/deps.py` | Add `get_pattern_library_repo` dependency provider |
| `backend/src/explorator/api/app.py` | Register `patterns.router` (order: after sessions, before catch-all / `{id}` routes) |
| `backend/src/explorator/api/routes/sessions.py` | Accept optional `genre` field on `CreateSessionRequest`; store in metadata |
| `backend/src/explorator/api/routes/rounds.py` | Read `warm_start_pattern_ids` from session metadata; pass into `initial_state` |
| `backend/src/explorator/engine/state.py` | Add `warm_start_pattern_ids: list[str]` and `warm_starts: dict[str, list[dict]]` fields |
| `backend/src/explorator/engine/graph.py` | Register `load_warm_starts` (after `parse_intent`/`load_genre`); register `harvest_patterns` (between `persist_realization` and `persist_round`); wire edges |
| `backend/src/explorator/engine/nodes/generate.py` | If `warm_starts['progression']` present, prepend the pattern's chord sequence as an initial candidate and reduce LLM `n_candidates` by 1 |
| `backend/src/explorator/engine/nodes/plan_voicings.py` | If `warm_starts['voicing']` present, seed one `VoicingPlan` per progression family from the pattern's abstracted parameters; LLM generates the remainder |
| `backend/src/explorator/engine/nodes/generate_bass.py` | If `warm_starts['bass']` present, seed one `BassLine` per progression family from the pattern's mode + density |
| `backend/src/explorator/engine/nodes/generate_groove.py` | If `warm_starts['groove']` present, seed one `GroovePattern` per progression family from the pattern's template |
| `backend/src/explorator/engine/nodes/generate_melody.py` | If `warm_starts['melody']` present, seed one `MelodicComplement` strategy per progression family from the pattern's contour + range + density |

### Frontend — create

| Path | Responsibility |
|------|---------------|
| `frontend/src/stores/patternLibraryStore.ts` | Zustand store: patterns list, filters, warm-start selections |
| `frontend/src/components/WarmStartPanel.tsx` | Shown on Dashboard after genre selection; lists available patterns by type; toggle selection; "Start Fresh" button |
| `frontend/src/components/PatternLibraryBrowser.tsx` | Full library view with filters by genre/type/tags; provenance link; delete button |
| `frontend/src/components/toastWrapper.ts` | Thin wrapper around Sonner `toast.success` / `toast.error` for consistent styling |
| `e2e/tests/warm-starts.spec.ts` | 6 Playwright tests covering harvest, browser, panel, seed, start-fresh, delete |

### Frontend — modify

| Path | Change |
|------|--------|
| `frontend/package.json` | Add `sonner` dependency |
| `frontend/src/App.tsx` | Mount `<Toaster />` from Sonner; add `/patterns` route → `PatternLibraryBrowser` |
| `frontend/src/services/api.ts` | Add `listPatterns`, `getPattern`, `deletePattern`, `getWarmStartSuggestions`, `setWarmStarts`, `harvestFinalists` |
| `frontend/src/views/Dashboard.tsx` | Add genre selector (if not already present); on genre pick, mount `WarmStartPanel`; submit includes genre + selected pattern IDs |
| `frontend/src/components/FinalistPanel.tsx` | Add "Save to library" button wired to `harvestFinalists`; show toast on success |
| `frontend/src/components/SessionWorkspace.tsx` | On SSE event `pattern_harvest`, show toast with count + library link |
| `frontend/src/views/Dashboard.tsx` | Add nav link to `/patterns` |

---

## Phase 1 — Data model & Neo4j schema

### Task 1: Update `PatternLibraryEntry` and `RetrievalQuery` models

**Files:**
- Modify: `backend/src/explorator/models/memory.py`
- Modify: `backend/tests/models/test_memory.py` (create if missing)

- [ ] **Step 1: Write failing test for updated model**

Create or append to `backend/tests/models/test_memory.py`:

```python
"""Tests for memory-related Pydantic models."""
from datetime import datetime
from explorator.models.memory import PatternLibraryEntry, RetrievalQuery
import pytest
from pydantic import ValidationError


def _now() -> datetime:
    return datetime.now()


def test_pattern_library_entry_requires_source_candidate_id():
    """source_candidate_id must be provided (no longer defaults to None)."""
    with pytest.raises(ValidationError):
        PatternLibraryEntry(
            id="pl_01",
            type="pattern_library_entry",
            created_at=_now(),
            updated_at=_now(),
            status="active",
            metadata={},
            pattern_type="progression",
            genre="house",
            # source_candidate_id omitted on purpose
        )


def test_pattern_library_entry_embedding_defaults_to_none():
    entry = PatternLibraryEntry(
        id="pl_01",
        type="pattern_library_entry",
        created_at=_now(),
        updated_at=_now(),
        status="active",
        metadata={},
        pattern_type="progression",
        genre="house",
        source_candidate_id="arr_01",
    )
    assert entry.embedding is None


def test_pattern_library_entry_accepts_embedding_list():
    entry = PatternLibraryEntry(
        id="pl_01",
        type="pattern_library_entry",
        created_at=_now(),
        updated_at=_now(),
        status="active",
        metadata={},
        pattern_type="progression",
        genre="house",
        source_candidate_id="arr_01",
        embedding=[0.1, 0.2, 0.3],
    )
    assert entry.embedding == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && uv run pytest tests/models/test_memory.py -v`
Expected: 3 new tests FAIL — one because `source_candidate_id` still accepts None, two because `embedding` field doesn't exist.

- [ ] **Step 3: Update model**

Edit `backend/src/explorator/models/memory.py`:

```python
class PatternLibraryEntry(BaseEntity):
    """Reusable discovered pattern harvested from a finalist candidate."""

    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str  # required — always harvested from a finalist
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    embedding: list[float] | None = None  # M5d: vector-readiness, null in graph-only mode
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/models/test_memory.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/models/memory.py backend/tests/models/test_memory.py
git commit -m "feat(m5d): require source_candidate_id, add embedding field to PatternLibraryEntry"
```

---

### Task 2: Add Neo4j schema indexes

**Files:**
- Modify: `backend/src/explorator/graph/schema.py`

- [ ] **Step 1: Inspect existing schema**

Run: `cd backend && grep -n "pattern_library" src/explorator/graph/schema.py`

Expected: one line (the existing `pattern_library_genre` index at around line 69).

- [ ] **Step 2: Add composite + pattern_type indexes**

Locate the existing `pattern_library_genre` line and add two siblings so the query path `WHERE entry.genre = $g AND entry.pattern_type = $pt` can hit a composite index.

Edit `backend/src/explorator/graph/schema.py`, replace the single existing pattern_library line with:

```python
"CREATE INDEX pattern_library_genre IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.genre)",
"CREATE INDEX pattern_library_pattern_type IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.pattern_type)",
"CREATE INDEX pattern_library_genre_type IF NOT EXISTS FOR (n:PatternLibraryEntry) ON (n.genre, n.pattern_type)",
```

- [ ] **Step 3: Verify migration applies cleanly against local Neo4j**

Run: `cd backend && uv run python -c "import asyncio; from explorator.graph.schema import apply_schema; from explorator.adapters.neo4j_client import get_driver; asyncio.run(apply_schema(get_driver()))"`

Expected: no error; indexes created (idempotent).

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/graph/schema.py
git commit -m "feat(m5d): add pattern_library composite and pattern_type indexes"
```

---

## Phase 2 — Neo4j repository

### Task 3: Create `PatternLibraryRepo` with upsert + get

**Files:**
- Create: `backend/src/explorator/graph/pattern_library_repo.py`
- Create: `backend/tests/graph/test_pattern_library_repo.py`

- [ ] **Step 1: Write failing tests for create + get**

Create `backend/tests/graph/test_pattern_library_repo.py`:

```python
"""Tests for PatternLibraryRepo."""
import pytest
from datetime import datetime

from explorator.models.memory import PatternLibraryEntry
from explorator.graph.pattern_library_repo import PatternLibraryRepo


@pytest.fixture
def sample_entry():
    return PatternLibraryEntry(
        id="pl_abc",
        type="pattern_library_entry",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status="active",
        metadata={},
        pattern_type="progression",
        genre="house",
        tags=["authentic_cadence", "loopability_high"],
        source_candidate_id="arr_01",
        abstracted_pattern={"chord_symbols": ["Cmaj7", "Am7", "Dm7", "G7"], "roman_numerals": ["Imaj7", "vi7", "ii7", "V7"]},
        success_metrics={"weighted_total": 0.82},
        notes="",
    )


@pytest.mark.asyncio
async def test_upsert_and_get(neo4j_driver, sample_entry):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(sample_entry)
    fetched = await repo.get_by_id(sample_entry.id)
    assert fetched is not None
    assert fetched["pattern_type"] == "progression"
    assert fetched["genre"] == "house"
    # Lists and dicts must round-trip correctly through Neo4j JSON serialization
    assert fetched["tags"] == ["authentic_cadence", "loopability_high"]
    assert fetched["abstracted_pattern"]["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]


@pytest.mark.asyncio
async def test_upsert_is_idempotent(neo4j_driver, sample_entry):
    """Calling upsert twice with the same id should not create duplicates."""
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(sample_entry)
    await repo.upsert(sample_entry)
    all_entries = await repo.list_all(genre="house")
    ids = [e["id"] for e in all_entries]
    assert ids.count(sample_entry.id) == 1
```

(The `neo4j_driver` fixture must exist — it's used by `test_groove_repo.py` and similar. Reuse the same import pattern as a nearby existing repo test.)

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v`
Expected: FAIL — repo module does not exist.

- [ ] **Step 3: Implement create + get**

Create `backend/src/explorator/graph/pattern_library_repo.py`:

```python
"""Neo4j repository for PatternLibraryEntry (M5d)."""
from typing import Any

from neo4j import AsyncDriver

from explorator.graph.repository import _neo4j_safe, _neo4j_deserialize
from explorator.models.memory import PatternLibraryEntry


class PatternLibraryRepo:
    """CRUD and query access for pattern library entries."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def upsert(self, entry: PatternLibraryEntry) -> None:
        """Create or update an entry. Idempotent by id."""
        props = _neo4j_safe(entry.model_dump())
        query = """
        MERGE (p:PatternLibraryEntry {id: $id})
        SET p += $props
        """
        async with self._driver.session() as neo_session:
            await neo_session.run(query, id=entry.id, props=props)

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
        clauses = []
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
        ORDER BY p.created_at DESC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            records = [r async for r in result]
            entries = [_neo4j_deserialize(dict(rec["p"])) for rec in records]

        # Tag filter is applied in Python because tags are stored as a JSON string;
        # Cypher can't index-filter through JSON. List filter is over small sets.
        if tags:
            entries = [e for e in entries if all(t in (e.get("tags") or []) for t in tags)]
        return entries
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/graph/test_pattern_library_repo.py
git commit -m "feat(m5d): add PatternLibraryRepo with upsert, get_by_id, list_all"
```

---

### Task 4: Add `delete_by_id` and `query_for_warm_starts` to repo

**Files:**
- Modify: `backend/src/explorator/graph/pattern_library_repo.py`
- Modify: `backend/tests/graph/test_pattern_library_repo.py`

- [ ] **Step 1: Add tests**

Append to `backend/tests/graph/test_pattern_library_repo.py`:

```python
@pytest.mark.asyncio
async def test_delete_by_id(neo4j_driver, sample_entry):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(sample_entry)
    await repo.delete_by_id(sample_entry.id)
    assert await repo.get_by_id(sample_entry.id) is None


@pytest.mark.asyncio
async def test_query_for_warm_starts_orders_by_weighted_total(neo4j_driver):
    """Warm-start query returns top_k entries per pattern_type ordered by weighted_total DESC."""
    repo = PatternLibraryRepo(neo4j_driver)
    now = datetime.now()

    def _entry(id_: str, score: float) -> PatternLibraryEntry:
        return PatternLibraryEntry(
            id=id_,
            type="pattern_library_entry",
            created_at=now,
            updated_at=now,
            status="active",
            metadata={},
            pattern_type="progression",
            genre="house",
            source_candidate_id="arr_01",
            abstracted_pattern={},
            success_metrics={"weighted_total": score},
        )

    await repo.upsert(_entry("pl_low", 0.5))
    await repo.upsert(_entry("pl_high", 0.9))
    await repo.upsert(_entry("pl_mid", 0.7))

    result = await repo.query_for_warm_starts(genre="house", top_k_per_type=2)

    progression = result.get("progression", [])
    assert [e["id"] for e in progression] == ["pl_high", "pl_mid"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && uv run pytest tests/graph/test_pattern_library_repo.py::test_delete_by_id tests/graph/test_pattern_library_repo.py::test_query_for_warm_starts_orders_by_weighted_total -v`
Expected: FAIL — methods do not exist.

- [ ] **Step 3: Implement both methods**

Append to `backend/src/explorator/graph/pattern_library_repo.py`:

```python
    async def delete_by_id(self, entry_id: str) -> None:
        query = "MATCH (p:PatternLibraryEntry {id: $id}) DETACH DELETE p"
        async with self._driver.session() as neo_session:
            await neo_session.run(query, id=entry_id)

    async def query_for_warm_starts(
        self,
        *,
        genre: str,
        top_k_per_type: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top-K patterns per pattern_type for a given genre.

        Ordering is by success_metrics.weighted_total DESC (parsed from JSON).
        Since success_metrics is stored as a JSON string, we fetch and sort in Python —
        the cardinality per-genre is small (tens to low-hundreds).
        """
        all_for_genre = await self.list_all(genre=genre)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in all_for_genre:
            grouped.setdefault(entry["pattern_type"], []).append(entry)
        for ptype, bucket in grouped.items():
            bucket.sort(
                key=lambda e: (e.get("success_metrics") or {}).get("weighted_total", 0.0),
                reverse=True,
            )
            grouped[ptype] = bucket[:top_k_per_type]
        return grouped
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/graph/test_pattern_library_repo.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py backend/tests/graph/test_pattern_library_repo.py
git commit -m "feat(m5d): add delete_by_id and query_for_warm_starts to PatternLibraryRepo"
```

---

## Phase 3 — Pattern harvesting service

### Task 5: Harvest a progression pattern from an arrangement candidate

**Files:**
- Create: `backend/src/explorator/services/pattern_harvesting.py`
- Create: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/services/test_pattern_harvesting.py`:

```python
"""Tests for pattern harvesting abstractions and tag generation."""
from explorator.services.pattern_harvesting import harvest_progression_pattern


def test_harvest_progression_pattern_basic():
    arrangement = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    progression = {
        "id": "prog_01",
        "key_center": "C",
        "mode": "major",
        "chord_symbols": ["Cmaj7", "Am7", "Dm7", "G7"],
        "phrase_length_bars": 4,
        "metadata": {"roman_numerals": ["Imaj7", "vi7", "ii7", "V7"]},
    }
    scorecard = {"weighted_total": 0.82, "scores": {"loopability": 0.9, "cadence_quality": 0.85}, "pareto_tags": ["pareto_front"]}

    entry = harvest_progression_pattern(
        arrangement=arrangement,
        progression=progression,
        scorecard=scorecard,
        genre="house",
        role="safest",
    )

    assert entry.pattern_type == "progression"
    assert entry.genre == "house"
    assert entry.source_candidate_id == "arr_01"
    assert entry.abstracted_pattern["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    assert entry.abstracted_pattern["roman_numerals"] == ["Imaj7", "vi7", "ii7", "V7"]
    assert entry.abstracted_pattern["key_center"] == "C"
    assert entry.abstracted_pattern["mode"] == "major"
    assert entry.abstracted_pattern["phrase_length_bars"] == 4
    assert entry.success_metrics["weighted_total"] == 0.82
    assert entry.success_metrics["loopability"] == 0.9


def test_harvest_progression_tags_include_loopability_bucket():
    """Loopability tag is bucketed: low (<0.4), mid (0.4-0.7), high (>=0.7)."""
    arrangement = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    progression = {"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4, "metadata": {}}

    high = harvest_progression_pattern(arrangement=arrangement, progression=progression, scorecard={"weighted_total": 0.8, "scores": {"loopability": 0.85}, "pareto_tags": []}, genre="house", role="safest")
    mid = harvest_progression_pattern(arrangement=arrangement, progression=progression, scorecard={"weighted_total": 0.6, "scores": {"loopability": 0.55}, "pareto_tags": []}, genre="house", role="safest")
    low = harvest_progression_pattern(arrangement=arrangement, progression=progression, scorecard={"weighted_total": 0.4, "scores": {"loopability": 0.2}, "pareto_tags": []}, genre="house", role="safest")

    assert "loopability_high" in high.tags
    assert "loopability_mid" in mid.tags
    assert "loopability_low" in low.tags


def test_harvest_progression_tags_include_role():
    """Finalist role is recorded as a tag for easy discovery."""
    arrangement = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    progression = {"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F"], "phrase_length_bars": 2, "metadata": {}}
    entry = harvest_progression_pattern(arrangement=arrangement, progression=progression, scorecard={"weighted_total": 0.7, "scores": {}, "pareto_tags": []}, genre="house", role="best_loop")

    assert "role:best_loop" in entry.tags
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the service**

Create `backend/src/explorator/services/pattern_harvesting.py`:

```python
"""Pattern harvesting: abstracts finalist candidates into PatternLibraryEntry rows."""
from datetime import datetime
from typing import Any

from ulid import ULID

from explorator.models.memory import PatternLibraryEntry
from explorator.utils import utc_now


def _loopability_bucket(value: float) -> str:
    if value >= 0.7:
        return "loopability_high"
    if value >= 0.4:
        return "loopability_mid"
    return "loopability_low"


def _new_id() -> str:
    return f"pl_{ULID()}"


def harvest_progression_pattern(
    *,
    arrangement: dict[str, Any],
    progression: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    """Abstract a progression into a reusable pattern with tags."""
    scores = scorecard.get("scores") or {}
    weighted_total = scorecard.get("weighted_total") or 0.0
    pareto_tags = scorecard.get("pareto_tags") or []

    tags: list[str] = [
        f"role:{role}",
        _loopability_bucket(scores.get("loopability", 0.0)),
    ]
    if "pareto_front" in pareto_tags:
        tags.append("pareto_front")

    abstracted = {
        "key_center": progression.get("key_center"),
        "mode": progression.get("mode"),
        "chord_symbols": progression.get("chord_symbols") or [],
        "roman_numerals": (progression.get("metadata") or {}).get("roman_numerals") or [],
        "phrase_length_bars": progression.get("phrase_length_bars"),
    }
    success_metrics = {"weighted_total": weighted_total, **{k: v for k, v in scores.items() if isinstance(v, (int, float))}}

    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type="progression",
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern=abstracted,
        success_metrics=success_metrics,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest progression patterns with role and loopability tags"
```

---

### Task 6: Harvest a voicing pattern

**Files:**
- Modify: `backend/src/explorator/services/pattern_harvesting.py`
- Modify: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_pattern_harvesting.py`:

```python
from explorator.services.pattern_harvesting import harvest_voicing_pattern


def test_harvest_voicing_pattern():
    arrangement = {"id": "arr_01", "voicing_plan_id": "vp_01"}
    voicing_plan = {
        "id": "vp_01",
        "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4},
        "voicings": [],  # opaque payload
    }
    scorecard = {"weighted_total": 0.8, "scores": {"voice_leading": 0.85, "register_density": 0.7}, "pareto_tags": []}

    entry = harvest_voicing_pattern(
        arrangement=arrangement,
        voicing_plan=voicing_plan,
        scorecard=scorecard,
        genre="house",
        role="safest",
    )

    assert entry.pattern_type == "voicing"
    assert entry.abstracted_pattern == {"register_profile": "mid", "density": "medium", "voice_count": 4}
    assert "register:mid" in entry.tags
    assert "density:medium" in entry.tags
    assert "voices:4" in entry.tags
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py::test_harvest_voicing_pattern -v`
Expected: FAIL — `harvest_voicing_pattern` not defined.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/services/pattern_harvesting.py`:

```python
def harvest_voicing_pattern(
    *,
    arrangement: dict[str, Any],
    voicing_plan: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    strategy = voicing_plan.get("strategy") or {}
    register = strategy.get("register_profile", "mid")
    density = strategy.get("density", "medium")
    voice_count = strategy.get("voice_count", 4)

    tags = [
        f"role:{role}",
        f"register:{register}",
        f"density:{density}",
        f"voices:{voice_count}",
    ]

    scores = scorecard.get("scores") or {}
    success_metrics = {
        "weighted_total": scorecard.get("weighted_total") or 0.0,
        **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
    }

    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type="voicing",
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern={"register_profile": register, "density": density, "voice_count": voice_count},
        success_metrics=success_metrics,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest voicing patterns"
```

---

### Task 7: Harvest a bass pattern

**Files:**
- Modify: `backend/src/explorator/services/pattern_harvesting.py`
- Modify: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_pattern_harvesting.py`:

```python
from explorator.services.pattern_harvesting import harvest_bass_pattern


def test_harvest_bass_pattern():
    arrangement = {"id": "arr_01", "bass_line_id": "bl_01"}
    bass_line = {"id": "bl_01", "mode": "walking", "rhythmic_density": 0.65, "notes": []}
    scorecard = {"weighted_total": 0.78, "scores": {"groove": 0.8}, "pareto_tags": []}

    entry = harvest_bass_pattern(
        arrangement=arrangement,
        bass_line=bass_line,
        scorecard=scorecard,
        genre="house",
        role="best_loop",
    )

    assert entry.pattern_type == "bass"
    assert entry.abstracted_pattern == {"mode": "walking", "rhythmic_density": 0.65}
    assert "bass_mode:walking" in entry.tags
    assert "rhythmic_density:mid" in entry.tags  # 0.65 is mid (0.4-0.7)


def test_harvest_bass_pattern_density_buckets():
    arrangement = {"id": "arr_01", "bass_line_id": "bl_01"}
    scorecard = {"weighted_total": 0.7, "scores": {}, "pareto_tags": []}

    dense = harvest_bass_pattern(arrangement=arrangement, bass_line={"id": "bl_01", "mode": "syncopated", "rhythmic_density": 0.85}, scorecard=scorecard, genre="house", role="safest")
    sparse = harvest_bass_pattern(arrangement=arrangement, bass_line={"id": "bl_01", "mode": "root", "rhythmic_density": 0.2}, scorecard=scorecard, genre="house", role="safest")

    assert "rhythmic_density:high" in dense.tags
    assert "rhythmic_density:low" in sparse.tags
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/services/pattern_harvesting.py`:

```python
def _density_bucket(value: float) -> str:
    if value >= 0.7:
        return "high"
    if value >= 0.4:
        return "mid"
    return "low"


def harvest_bass_pattern(
    *,
    arrangement: dict[str, Any],
    bass_line: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    mode = bass_line.get("mode", "root")
    density = bass_line.get("rhythmic_density", 0.5)

    tags = [
        f"role:{role}",
        f"bass_mode:{mode}",
        f"rhythmic_density:{_density_bucket(density)}",
    ]

    scores = scorecard.get("scores") or {}
    success_metrics = {
        "weighted_total": scorecard.get("weighted_total") or 0.0,
        **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
    }

    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type="bass",
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern={"mode": mode, "rhythmic_density": density},
        success_metrics=success_metrics,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest bass patterns with density buckets"
```

---

### Task 8: Harvest a groove pattern

**Files:**
- Modify: `backend/src/explorator/services/pattern_harvesting.py`
- Modify: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Test**

Append to `backend/tests/services/test_pattern_harvesting.py`:

```python
from explorator.services.pattern_harvesting import harvest_groove_pattern


def test_harvest_groove_pattern():
    arrangement = {"id": "arr_01", "groove_pattern_id": "gp_01"}
    groove = {"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    scorecard = {"weighted_total": 0.8, "scores": {"groove": 0.9}, "pareto_tags": ["pareto_front"]}

    entry = harvest_groove_pattern(arrangement=arrangement, groove=groove, scorecard=scorecard, genre="house", role="safest")

    assert entry.pattern_type == "groove"
    assert entry.abstracted_pattern == {"swing_level": 0.4, "syncopation_level": 0.6, "density": 0.7, "template_name": "house_basic"}
    assert "swing:mid" in entry.tags
    assert "syncopation:mid" in entry.tags
    assert "density:high" in entry.tags
    assert "template:house_basic" in entry.tags
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py::test_harvest_groove_pattern -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/services/pattern_harvesting.py`:

```python
def harvest_groove_pattern(
    *,
    arrangement: dict[str, Any],
    groove: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    swing = groove.get("swing_level", 0.0)
    sync = groove.get("syncopation_level", 0.0)
    density = groove.get("density", 0.5)
    template = groove.get("template_name", "")

    tags = [
        f"role:{role}",
        f"swing:{_density_bucket(swing)}",
        f"syncopation:{_density_bucket(sync)}",
        f"density:{_density_bucket(density)}",
    ]
    if template:
        tags.append(f"template:{template}")

    scores = scorecard.get("scores") or {}
    success_metrics = {
        "weighted_total": scorecard.get("weighted_total") or 0.0,
        **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
    }

    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type="groove",
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern={
            "swing_level": swing,
            "syncopation_level": sync,
            "density": density,
            "template_name": template,
        },
        success_metrics=success_metrics,
    )
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest groove patterns"
```

---

### Task 9: Harvest a melody pattern

**Files:**
- Modify: `backend/src/explorator/services/pattern_harvesting.py`
- Modify: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Test**

Append:

```python
from explorator.services.pattern_harvesting import harvest_melody_pattern


def test_harvest_melody_pattern():
    arrangement = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    melody = {
        "id": "mc_01",
        "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5},
        "notes": [],
    }
    scorecard = {"weighted_total": 0.76, "scores": {"melody_support": 0.82}, "pareto_tags": []}

    entry = harvest_melody_pattern(arrangement=arrangement, melody=melody, scorecard=scorecard, genre="house", role="most_experimental")

    assert entry.pattern_type == "melody"
    assert entry.abstracted_pattern == {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}
    assert "contour:arch" in entry.tags
    assert "range:medium" in entry.tags  # 12 <= 14 < 19 = medium
    assert "melody_density:mid" in entry.tags


def test_harvest_melody_range_buckets():
    """Range buckets: narrow (<12 st), medium (12-18 st), wide (>=19 st)."""
    arrangement = {"id": "arr_01", "melodic_complement_id": "mc_01"}
    scorecard = {"weighted_total": 0.7, "scores": {}, "pareto_tags": []}

    narrow = harvest_melody_pattern(arrangement=arrangement, melody={"id": "mc_01", "strategy": {"contour_type": "ascending", "range_semitones": 7, "rhythmic_density": 0.5}}, scorecard=scorecard, genre="house", role="safest")
    wide = harvest_melody_pattern(arrangement=arrangement, melody={"id": "mc_01", "strategy": {"contour_type": "descending", "range_semitones": 24, "rhythmic_density": 0.5}}, scorecard=scorecard, genre="house", role="safest")

    assert "range:narrow" in narrow.tags
    assert "range:wide" in wide.tags
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Append:

```python
def _range_bucket(semitones: int) -> str:
    if semitones >= 19:
        return "wide"
    if semitones >= 12:
        return "medium"
    return "narrow"


def harvest_melody_pattern(
    *,
    arrangement: dict[str, Any],
    melody: dict[str, Any],
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> PatternLibraryEntry:
    strategy = melody.get("strategy") or {}
    contour = strategy.get("contour_type", "")
    rng = int(strategy.get("range_semitones", 12))
    density = float(strategy.get("rhythmic_density", 0.5))

    tags = [
        f"role:{role}",
        f"contour:{contour}",
        f"range:{_range_bucket(rng)}",
        f"melody_density:{_density_bucket(density)}",
    ]

    scores = scorecard.get("scores") or {}
    success_metrics = {
        "weighted_total": scorecard.get("weighted_total") or 0.0,
        **{k: v for k, v in scores.items() if isinstance(v, (int, float))},
    }

    now = utc_now()
    return PatternLibraryEntry(
        id=_new_id(),
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type="melody",
        genre=genre,
        tags=tags,
        source_candidate_id=arrangement["id"],
        abstracted_pattern={"contour_type": contour, "range_semitones": rng, "rhythmic_density": density},
        success_metrics=success_metrics,
    )
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): harvest melody patterns with contour and range tags"
```

---

### Task 10: Top-level `harvest_finalist` orchestrator

Orchestrates all five per-type harvesters for a single finalist arrangement.

**Files:**
- Modify: `backend/src/explorator/services/pattern_harvesting.py`
- Modify: `backend/tests/services/test_pattern_harvesting.py`

- [ ] **Step 1: Test**

Append:

```python
from explorator.services.pattern_harvesting import harvest_finalist


def test_harvest_finalist_produces_one_entry_per_facet():
    """Given a complete finalist arrangement, produce 5 entries (one per type)."""
    arrangement = {
        "id": "arr_01",
        "progression_candidate_id": "prog_01",
        "voicing_plan_id": "vp_01",
        "bass_line_id": "bl_01",
        "groove_pattern_id": "gp_01",
        "melodic_complement_id": "mc_01",
    }
    progression = {"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F"], "phrase_length_bars": 2, "metadata": {}}
    voicing_plan = {"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}
    bass_line = {"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6}
    groove = {"id": "gp_01", "swing_level": 0.4, "syncopation_level": 0.5, "density": 0.7, "template_name": "house_basic"}
    melody = {"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}
    scorecard = {"weighted_total": 0.8, "scores": {"loopability": 0.8}, "pareto_tags": []}

    entries = harvest_finalist(
        arrangement=arrangement,
        progression=progression,
        voicing_plan=voicing_plan,
        bass_line=bass_line,
        groove=groove,
        melody=melody,
        scorecard=scorecard,
        genre="house",
        role="safest",
    )

    types = [e.pattern_type for e in entries]
    assert sorted(types) == ["bass", "groove", "melody", "progression", "voicing"]


def test_harvest_finalist_skips_missing_facets():
    """If a facet is absent (e.g. no groove), don't emit an entry for it."""
    arrangement = {"id": "arr_01", "progression_candidate_id": "prog_01"}
    progression = {"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F"], "phrase_length_bars": 2, "metadata": {}}
    scorecard = {"weighted_total": 0.8, "scores": {}, "pareto_tags": []}

    entries = harvest_finalist(
        arrangement=arrangement,
        progression=progression,
        voicing_plan=None,
        bass_line=None,
        groove=None,
        melody=None,
        scorecard=scorecard,
        genre="house",
        role="safest",
    )

    assert [e.pattern_type for e in entries] == ["progression"]
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Append:

```python
def harvest_finalist(
    *,
    arrangement: dict[str, Any],
    progression: dict[str, Any],
    voicing_plan: dict[str, Any] | None,
    bass_line: dict[str, Any] | None,
    groove: dict[str, Any] | None,
    melody: dict[str, Any] | None,
    scorecard: dict[str, Any],
    genre: str,
    role: str,
) -> list[PatternLibraryEntry]:
    """Produce one entry per facet present on the arrangement."""
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

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_harvesting.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_harvesting.py backend/tests/services/test_pattern_harvesting.py
git commit -m "feat(m5d): add harvest_finalist orchestrator"
```

---

## Phase 4 — Harvest LangGraph node + wiring

### Task 11: Extend `ExplorationState` with warm-start fields

**Files:**
- Modify: `backend/src/explorator/engine/state.py`

- [ ] **Step 1: Add fields**

Edit `backend/src/explorator/engine/state.py` — append to `ExplorationState`:

```python
    # --- M5d: Retrieval-Assisted Warm Starts ---
    warm_start_pattern_ids: list[str]
    # After load_warm_starts runs, this dict maps pattern_type -> list of entries.
    # Generation nodes read from here to decide whether to pre-seed a slot.
    warm_starts: dict[str, list[dict[str, Any]]]
    # After harvest_patterns runs, IDs of newly persisted entries (for SSE/UI).
    harvested_pattern_ids: list[str]
```

- [ ] **Step 2: Type-check**

Run: `cd backend && uv run mypy src/explorator/engine/state.py`
Expected: no new errors. (If mypy isn't configured, `uv run python -c "from explorator.engine.state import ExplorationState; print(ExplorationState.__annotations__)"` — should list the new fields.)

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/state.py
git commit -m "feat(m5d): add warm-start and harvest state fields to ExplorationState"
```

---

### Task 12: Create `harvest_patterns` LangGraph node

**Files:**
- Create: `backend/src/explorator/engine/nodes/harvest_patterns.py`
- Create: `backend/tests/engine/nodes/test_harvest_patterns.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_harvest_patterns.py`:

```python
"""Tests for the harvest_patterns LangGraph node."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.harvest_patterns import harvest_patterns


@pytest.mark.asyncio
async def test_harvest_patterns_persists_entries_for_each_finalist():
    """Each finalist arrangement in final_selection should produce up to 5 entries."""
    state = {
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
        "progression_candidates": [{"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F"], "phrase_length_bars": 2, "metadata": {}}],
        "voicing_plans": [{"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}],
        "bass_lines": [{"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6}],
        "groove_patterns": [{"id": "gp_01", "swing_level": 0.3, "syncopation_level": 0.4, "density": 0.6, "template_name": "house_basic"}],
        "melodic_complements": [{"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}],
        "scorecards": [{"candidate_id": "arr_01", "weighted_total": 0.8, "scores": {"loopability": 0.8}, "pareto_tags": []}],
        "on_progress": AsyncMock(),
    }

    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)

    # 5 upserts for one finalist with all facets
    assert repo.upsert.await_count == 5
    assert len(result["harvested_pattern_ids"]) == 5
    # Progress event was emitted
    state["on_progress"].assert_awaited_with("pattern_harvest", {"count": 5, "genre": "house"})


@pytest.mark.asyncio
async def test_harvest_patterns_skips_when_no_final_selection():
    """If final_selection is empty or missing, node is a no-op."""
    state = {"session_id": "sess_01", "genre": "house", "final_selection": {"selected_candidate_ids": []}, "arrangement_candidates": []}
    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)
    repo.upsert.assert_not_awaited()
    assert result["harvested_pattern_ids"] == []
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_harvest_patterns.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/engine/nodes/harvest_patterns.py`:

```python
"""LangGraph node: auto-harvest patterns from finalist arrangements."""
from typing import Any

from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.services.pattern_harvesting import harvest_finalist


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


async def harvest_patterns(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    """Extract PatternLibraryEntry per finalist facet and persist to Neo4j."""
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
        for entry in entries:
            await repo.upsert(entry)
            harvested_ids.append(entry.id)

    on_progress = state.get("on_progress")
    if on_progress is not None:
        await on_progress("pattern_harvest", {"count": len(harvested_ids), "genre": genre})

    return {"harvested_pattern_ids": harvested_ids}
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_harvest_patterns.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/harvest_patterns.py backend/tests/engine/nodes/test_harvest_patterns.py
git commit -m "feat(m5d): add harvest_patterns LangGraph node"
```

---

### Task 13: Wire `harvest_patterns` into the main exploration graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/tests/engine/test_graph.py` (or create)

- [ ] **Step 1: Add a test asserting the node is present and edged correctly**

Append to (or create) `backend/tests/engine/test_graph.py`:

```python
def test_exploration_graph_contains_harvest_patterns_node_between_persist_realization_and_persist_round():
    """harvest_patterns must run after persist_realization and before persist_round."""
    from unittest.mock import MagicMock
    from explorator.engine.graph import build_exploration_graph

    gemini = MagicMock()
    driver = MagicMock()
    graph = build_exploration_graph(gemini, driver)
    nodes = set(graph.get_graph().nodes)
    assert "harvest_patterns" in nodes

    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("persist_realization", "harvest_patterns") in edges
    assert ("harvest_patterns", "persist_round") in edges
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/engine/test_graph.py::test_exploration_graph_contains_harvest_patterns_node_between_persist_realization_and_persist_round -v`
Expected: FAIL.

- [ ] **Step 3: Register node and change edges**

Edit `backend/src/explorator/engine/graph.py`:

Import the node next to the others:
```python
from explorator.engine.nodes.harvest_patterns import harvest_patterns
from explorator.graph.pattern_library_repo import PatternLibraryRepo
```

Inside `build_exploration_graph`, add the node just after `persist_realization` registration:
```python
    graph.add_node(
        "harvest_patterns",
        partial(harvest_patterns, repo=PatternLibraryRepo(driver)),
    )
```

Replace the final edges:
```python
    graph.add_edge("persist_realization", "persist_round")
```
with:
```python
    graph.add_edge("persist_realization", "harvest_patterns")
    graph.add_edge("harvest_patterns", "persist_round")
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/test_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/engine/test_graph.py
git commit -m "feat(m5d): wire harvest_patterns between persist_realization and persist_round"
```

---

## Phase 5 — Retrieval + warm-start loading node

### Task 14: Create `GraphRetrieval` strategy

**Files:**
- Create: `backend/src/explorator/services/pattern_retrieval.py`
- Create: `backend/tests/services/test_pattern_retrieval.py`

- [ ] **Step 1: Test**

Create `backend/tests/services/test_pattern_retrieval.py`:

```python
"""Tests for GraphRetrieval strategy."""
from unittest.mock import AsyncMock

import pytest

from explorator.services.pattern_retrieval import GraphRetrieval


@pytest.mark.asyncio
async def test_graph_retrieval_groups_results_by_pattern_type():
    repo = AsyncMock()
    repo.query_for_warm_starts.return_value = {
        "progression": [{"id": "pl_1"}, {"id": "pl_2"}],
        "voicing": [{"id": "pl_3"}],
    }
    strategy = GraphRetrieval(repo=repo)

    result = await strategy.fetch(genre="house", top_k_per_type=5)

    assert set(result.keys()) == {"progression", "voicing"}
    assert [e["id"] for e in result["progression"]] == ["pl_1", "pl_2"]
    repo.query_for_warm_starts.assert_awaited_once_with(genre="house", top_k_per_type=5)


@pytest.mark.asyncio
async def test_graph_retrieval_returns_empty_dict_when_no_patterns():
    repo = AsyncMock()
    repo.query_for_warm_starts.return_value = {}
    strategy = GraphRetrieval(repo=repo)
    assert await strategy.fetch(genre="house") == {}
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_retrieval.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/services/pattern_retrieval.py`:

```python
"""Pattern retrieval strategies. M5d ships GraphRetrieval; VectorRetrieval is a future swap."""
from typing import Any, Protocol

from explorator.graph.pattern_library_repo import PatternLibraryRepo


class RetrievalStrategy(Protocol):
    """Interface allowing VectorRetrieval to swap in later without changing callers."""

    async def fetch(self, *, genre: str, top_k_per_type: int = 5) -> dict[str, list[dict[str, Any]]]: ...


class GraphRetrieval:
    """Neo4j graph-backed retrieval: filters by genre, orders by weighted_total."""

    def __init__(self, *, repo: PatternLibraryRepo) -> None:
        self._repo = repo

    async def fetch(self, *, genre: str, top_k_per_type: int = 5) -> dict[str, list[dict[str, Any]]]:
        return await self._repo.query_for_warm_starts(genre=genre, top_k_per_type=top_k_per_type)
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/services/test_pattern_retrieval.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/services/pattern_retrieval.py backend/tests/services/test_pattern_retrieval.py
git commit -m "feat(m5d): add GraphRetrieval strategy for pattern warm-starts"
```

---

### Task 15: Create `load_warm_starts` LangGraph node

**Files:**
- Create: `backend/src/explorator/engine/nodes/load_warm_starts.py`
- Create: `backend/tests/engine/nodes/test_load_warm_starts.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_load_warm_starts.py`:

```python
"""Tests for load_warm_starts node."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.load_warm_starts import load_warm_starts


@pytest.mark.asyncio
async def test_load_warm_starts_groups_entries_by_pattern_type():
    state = {"warm_start_pattern_ids": ["pl_1", "pl_2", "pl_3"]}
    repo = AsyncMock()
    repo.get_by_id.side_effect = [
        {"id": "pl_1", "pattern_type": "progression", "abstracted_pattern": {"x": 1}},
        {"id": "pl_2", "pattern_type": "voicing", "abstracted_pattern": {"y": 2}},
        {"id": "pl_3", "pattern_type": "progression", "abstracted_pattern": {"x": 3}},
    ]

    result = await load_warm_starts(state, repo=repo)

    ws = result["warm_starts"]
    assert sorted(ws.keys()) == ["progression", "voicing"]
    assert len(ws["progression"]) == 2
    assert len(ws["voicing"]) == 1


@pytest.mark.asyncio
async def test_load_warm_starts_empty_when_no_ids():
    """Missing or empty pattern IDs produces an empty warm_starts dict."""
    repo = AsyncMock()
    result = await load_warm_starts({}, repo=repo)
    assert result == {"warm_starts": {}}
    repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_warm_starts_silently_drops_missing_ids():
    """Stale pattern_ids (pattern deleted between session create and rounds) are dropped."""
    state = {"warm_start_pattern_ids": ["pl_gone", "pl_ok"]}
    repo = AsyncMock()
    repo.get_by_id.side_effect = [None, {"id": "pl_ok", "pattern_type": "bass", "abstracted_pattern": {}}]
    result = await load_warm_starts(state, repo=repo)
    assert list(result["warm_starts"].keys()) == ["bass"]
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_load_warm_starts.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `backend/src/explorator/engine/nodes/load_warm_starts.py`:

```python
"""LangGraph node: hydrate warm-start pattern entries from Neo4j into state."""
from typing import Any

from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo


async def load_warm_starts(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    ids: list[str] = state.get("warm_start_pattern_ids") or []
    if not ids:
        return {"warm_starts": {}}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for pid in ids:
        entry = await repo.get_by_id(pid)
        if entry is None:
            continue
        ptype = entry.get("pattern_type")
        if not ptype:
            continue
        grouped.setdefault(ptype, []).append(entry)
    return {"warm_starts": grouped}
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_load_warm_starts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/load_warm_starts.py backend/tests/engine/nodes/test_load_warm_starts.py
git commit -m "feat(m5d): add load_warm_starts LangGraph node"
```

---

### Task 16: Wire `load_warm_starts` into the graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/tests/engine/test_graph.py`

- [ ] **Step 1: Test**

Append to `backend/tests/engine/test_graph.py`:

```python
def test_exploration_graph_runs_load_warm_starts_between_load_memory_and_generate():
    from unittest.mock import MagicMock
    from explorator.engine.graph import build_exploration_graph

    graph = build_exploration_graph(MagicMock(), MagicMock())
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("load_memory", "load_warm_starts") in edges
    assert ("load_warm_starts", "generate") in edges
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/test_graph.py::test_exploration_graph_runs_load_warm_starts_between_load_memory_and_generate -v`
Expected: FAIL.

- [ ] **Step 3: Edit graph**

In `backend/src/explorator/engine/graph.py`, add imports:
```python
from explorator.engine.nodes.load_warm_starts import load_warm_starts
```

Inside `build_exploration_graph`, add node registration (after `load_memory` node):
```python
    graph.add_node(
        "load_warm_starts",
        partial(load_warm_starts, repo=PatternLibraryRepo(driver)),
    )
```

Replace the edge `graph.add_edge("load_memory", "generate")` with:
```python
    graph.add_edge("load_memory", "load_warm_starts")
    graph.add_edge("load_warm_starts", "generate")
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/test_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/engine/test_graph.py
git commit -m "feat(m5d): wire load_warm_starts between load_memory and generate"
```

---

## Phase 6 — Generation node warm-start seeding

Each of the five generation nodes is extended to pre-seed one slot per progression family from matching warm-start data. The pattern here:

- Read `state['warm_starts'].get(<pattern_type>, [])`.
- For each warm-start entry, construct a pre-built domain object and prepend it to the node's output list.
- Reduce the LLM's candidate count by the number of pre-seeded slots (for `generate`, which is the only node with a round-1 batch concept — others are per-family).

### Task 17: Seed a progression warm-start in `generate`

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate.py`
- Create: `backend/tests/engine/nodes/test_generate_warm_start.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_generate_warm_start.py`:

```python
"""Warm-start injection tests for the generate node."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.generate import generate


@pytest.mark.asyncio
async def test_generate_prepends_warm_start_progression_and_reduces_llm_count():
    """When a progression warm-start exists, LLM produces n-1 candidates and the warm-start is candidate #1."""
    gemini = AsyncMock()
    # LLM returns 2 synthetic candidates (so we can assert we received n-1=2)
    gemini.generate_json.return_value = {"progressions": [
        {"key_center": "C", "mode": "major", "chord_symbols": ["C", "G"], "phrase_length_bars": 2, "rationale": ""},
        {"key_center": "C", "mode": "major", "chord_symbols": ["F", "C"], "phrase_length_bars": 2, "rationale": ""},
    ]}

    state = {
        "session_id": "sess_01",
        "genre": "house",
        "genre_profile": {},
        "harmonic_grammar": {},
        "creative_brief": {"genre": "house", "key_center": "C", "mode": "major", "phrase_length_bars": 2},
        "generation_mode": "balanced",
        "n_candidates": 3,
        "round_number": 1,
        "warm_starts": {
            "progression": [{
                "id": "pl_seed",
                "pattern_type": "progression",
                "abstracted_pattern": {
                    "key_center": "C",
                    "mode": "major",
                    "chord_symbols": ["Cmaj7", "Am7", "Dm7", "G7"],
                    "phrase_length_bars": 4,
                    "roman_numerals": ["Imaj7", "vi7", "ii7", "V7"],
                },
            }],
        },
    }

    result = await generate(state, gemini=gemini)

    candidates = result["progression_candidates"]
    assert len(candidates) == 3
    # Warm-start pattern became the first candidate — verify by distinctive chord sequence
    assert candidates[0]["chord_symbols"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    # Warm-start source is recorded in metadata for provenance
    assert candidates[0]["metadata"].get("warm_start_pattern_id") == "pl_seed"
    # LLM was called asking for n-1=2 candidates
    _, kwargs = gemini.generate_json.call_args
    assert "2" in str(kwargs.get("prompt", "")) or kwargs.get("prompt_context", {}).get("n_candidates") == 2 \
        or gemini.generate_json.call_args.kwargs.get("n_candidates") == 2  # prompt format may vary — see note below
```

**Note for implementer:** The exact assertion on the LLM call depends on how `generate.py` composes its prompt (inline number in the prompt string vs. a structured kwarg). Read `backend/src/explorator/engine/nodes/generate.py` first, then write the assertion to match the actual call shape. The important invariant is "LLM was asked for `n_candidates - len(warm_start_progressions)`".

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_warm_start.py -v`
Expected: FAIL.

- [ ] **Step 3: Read the existing `generate` node and adapt**

Read `backend/src/explorator/engine/nodes/generate.py`. The changes are:

1. At the top of the function, read `warm_starts = state.get("warm_starts") or {}` and `progression_seeds = warm_starts.get("progression") or []`.
2. Pre-build one `ProgressionCandidate` dict per seed:
   - `id = f"prog_{ULID()}"`
   - `session_id = state["session_id"]`
   - `type = "progression_candidate"`
   - Copy `key_center`, `mode`, `chord_symbols`, `phrase_length_bars` from the abstracted pattern.
   - `generator_mode = "warm_start"`
   - `rationale = "Seeded from pattern library entry <id>"`
   - `metadata = {"warm_start_pattern_id": seed["id"], "roman_numerals": abstracted.get("roman_numerals", [])}`
   - Other fields use existing defaults already used by the LLM path in the same file.
3. Request `n_llm = max(0, n_candidates - len(seeds))` from the LLM instead of `n_candidates`.
4. Concatenate: `seeds_as_candidates + llm_candidates`.
5. Return `{"progression_candidates": seeds_as_candidates + llm_candidates}` (preserving the existing return shape).

Apply these edits in the smallest way that keeps the existing non-warm-start behavior identical (i.e. if `seeds == []`, behavior must be unchanged).

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_warm_start.py tests/engine/nodes/test_generate.py -v`
Expected: new test PASSES; existing `test_generate.py` continues to PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate.py backend/tests/engine/nodes/test_generate_warm_start.py
git commit -m "feat(m5d): seed progression warm-start as pre-built candidate in generate"
```

---

### Task 18: Seed a voicing warm-start in `plan_voicings`

**Files:**
- Modify: `backend/src/explorator/engine/nodes/plan_voicings.py`
- Create: `backend/tests/engine/nodes/test_plan_voicings_warm_start.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_plan_voicings_warm_start.py`:

```python
"""Warm-start injection tests for plan_voicings."""
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.plan_voicings import plan_voicings


@pytest.mark.asyncio
async def test_plan_voicings_adds_warm_start_strategy_per_progression_family(monkeypatch):
    """With a voicing warm-start, each progression family gets one extra voicing plan built from the abstracted params."""
    gemini = AsyncMock()
    gemini.generate_json.return_value = {"voicing_plans": []}  # normal LLM strategies — irrelevant for this test

    state = {
        "session_id": "sess_01",
        "genre": "house",
        "top_progressions": [{"id": "prog_01", "key_center": "C", "mode": "major", "chord_symbols": ["C", "F", "G", "C"]}],
        "voicing_strategies": [],
        "warm_starts": {
            "voicing": [{
                "id": "pl_vseed",
                "pattern_type": "voicing",
                "abstracted_pattern": {"register_profile": "mid", "density": "sparse", "voice_count": 3},
            }],
        },
    }

    result = await plan_voicings(state, gemini=gemini)

    seeded = [vp for vp in result["voicing_plans"] if vp.get("metadata", {}).get("warm_start_pattern_id") == "pl_vseed"]
    assert len(seeded) == 1  # one per progression family
    assert seeded[0]["progression_candidate_id"] == "prog_01"
    assert seeded[0]["strategy"]["register_profile"] == "mid"
    assert seeded[0]["strategy"]["density"] == "sparse"
    assert seeded[0]["strategy"]["voice_count"] == 3
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_plan_voicings_warm_start.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `plan_voicings.py`**

Read the file, then add: at the top, pull `warm_starts = state.get("warm_starts") or {}` and `voicing_seeds = warm_starts.get("voicing") or []`. After the LLM-produced plans are built (but inside the same function, before returning), for each progression in `top_progressions` and each seed, append:

```python
{
    "id": f"vp_{ULID()}",
    "type": "voicing_plan",
    "created_at": now,
    "updated_at": now,
    "status": "active",
    "version": 1,
    "metadata": {"warm_start_pattern_id": seed["id"]},
    "progression_candidate_id": progression["id"],
    "strategy": {
        "register_profile": seed["abstracted_pattern"].get("register_profile", "mid"),
        "density": seed["abstracted_pattern"].get("density", "medium"),
        "voice_count": seed["abstracted_pattern"].get("voice_count", 4),
    },
    # Voicings list is left empty; realization layer will materialize based on strategy + progression.
    "voicings": [],
}
```

Use whatever helpers the file already has (e.g., `utc_now()`, `ULID`). Match existing field names by reading the file first.

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_plan_voicings_warm_start.py tests/engine/nodes/test_plan_voicings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/plan_voicings.py backend/tests/engine/nodes/test_plan_voicings_warm_start.py
git commit -m "feat(m5d): seed voicing warm-start per progression family in plan_voicings"
```

---

### Task 19: Seed a bass warm-start in `generate_bass`

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_bass.py`
- Create: `backend/tests/engine/nodes/test_generate_bass_warm_start.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_generate_bass_warm_start.py`:

```python
"""Warm-start injection tests for generate_bass."""
import pytest

from explorator.engine.nodes.generate_bass import generate_bass


@pytest.mark.asyncio
async def test_generate_bass_seeds_one_warm_start_bass_per_voicing_plan():
    state = {
        "session_id": "sess_01",
        "top_progressions": [{"id": "prog_01", "chord_symbols": ["C", "F", "G", "C"], "key_center": "C", "mode": "major"}],
        "voicing_plans": [{"id": "vp_01", "progression_candidate_id": "prog_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}, "voicings": []}],
        "warm_starts": {
            "bass": [{
                "id": "pl_bseed",
                "pattern_type": "bass",
                "abstracted_pattern": {"mode": "walking", "rhythmic_density": 0.65},
            }],
        },
    }

    result = await generate_bass(state)

    seeded = [bl for bl in result["bass_lines"] if bl.get("metadata", {}).get("warm_start_pattern_id") == "pl_bseed"]
    assert len(seeded) == 1
    assert seeded[0]["mode"] == "walking"
    assert seeded[0]["rhythmic_density"] == 0.65
    assert seeded[0]["voicing_plan_id"] == "vp_01"
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_bass_warm_start.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `generate_bass.py`**

Read the file; then after normal bass lines are built, for each seed × voicing_plan, append a minimally-populated `BassLine`-shaped dict copying `mode` and `rhythmic_density` from the seed and using the standard deterministic note-placement logic already in the file (or set `notes: []` if the file's layer uses a downstream realizer).

The returned dict must include:
```python
{
    "id": f"bl_{ULID()}",
    "type": "bass_line",
    ...base entity fields...
    "metadata": {"warm_start_pattern_id": seed["id"]},
    "voicing_plan_id": vp["id"],
    "mode": seed["abstracted_pattern"].get("mode", "root"),
    "rhythmic_density": seed["abstracted_pattern"].get("rhythmic_density", 0.5),
    "notes": [],
}
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_bass_warm_start.py tests/engine/nodes/test_generate_bass.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_bass.py backend/tests/engine/nodes/test_generate_bass_warm_start.py
git commit -m "feat(m5d): seed bass warm-start per voicing plan in generate_bass"
```

---

### Task 20: Seed a groove warm-start in `generate_groove`

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_groove.py`
- Create: `backend/tests/engine/nodes/test_generate_groove_warm_start.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_generate_groove_warm_start.py`:

```python
import pytest

from explorator.engine.nodes.generate_groove import generate_groove


@pytest.mark.asyncio
async def test_generate_groove_seeds_warm_start_per_progression_family():
    state = {
        "session_id": "sess_01",
        "top_progressions": [{"id": "prog_01", "chord_symbols": ["C", "F", "G", "C"]}],
        "warm_starts": {
            "groove": [{
                "id": "pl_gseed",
                "pattern_type": "groove",
                "abstracted_pattern": {"swing_level": 0.3, "syncopation_level": 0.5, "density": 0.7, "template_name": "house_basic"},
            }],
        },
    }

    result = await generate_groove(state)
    seeded = [g for g in result["groove_patterns"] if g.get("metadata", {}).get("warm_start_pattern_id") == "pl_gseed"]
    assert len(seeded) == 1
    assert seeded[0]["swing_level"] == 0.3
    assert seeded[0]["template_name"] == "house_basic"
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_groove_warm_start.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `generate_groove.py`**

After the normal deterministic grooves are produced, for each seed × progression_family, append a `GroovePattern`-shaped dict with the seed's parameters copied in. Use the existing helpers in the file for any required fields (events, velocities, etc. — leave empty if the realization layer fills them).

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_groove_warm_start.py tests/engine/nodes/test_generate_groove.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_groove.py backend/tests/engine/nodes/test_generate_groove_warm_start.py
git commit -m "feat(m5d): seed groove warm-start per progression family"
```

---

### Task 21: Seed a melody warm-start in `generate_melody`

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate_melody.py`
- Create: `backend/tests/engine/nodes/test_generate_melody_warm_start.py`

- [ ] **Step 1: Test**

Create `backend/tests/engine/nodes/test_generate_melody_warm_start.py`:

```python
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.generate_melody import generate_melody


@pytest.mark.asyncio
async def test_generate_melody_seeds_warm_start_strategy_per_arrangement():
    gemini = AsyncMock()
    gemini.generate_json.return_value = {"melody_strategies": []}

    state = {
        "session_id": "sess_01",
        "arrangement_candidates": [{"id": "arr_01", "progression_candidate_id": "prog_01", "voicing_plan_id": "vp_01", "bass_line_id": "bl_01", "groove_pattern_id": "gp_01"}],
        "top_progressions": [{"id": "prog_01", "chord_symbols": ["C", "F", "G", "C"]}],
        "groove_patterns": [{"id": "gp_01"}],
        "warm_starts": {
            "melody": [{
                "id": "pl_mseed",
                "pattern_type": "melody",
                "abstracted_pattern": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5},
            }],
        },
    }

    result = await generate_melody(state, gemini=gemini)
    seeded = [m for m in result["melodic_complements"] if m.get("metadata", {}).get("warm_start_pattern_id") == "pl_mseed"]
    assert len(seeded) == 1
    assert seeded[0]["strategy"]["contour_type"] == "arch"
    assert seeded[0]["strategy"]["range_semitones"] == 14
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_melody_warm_start.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `generate_melody.py`**

Read the file. Generate_melody operates per arrangement candidate. For each seed × arrangement_candidate, append a `MelodicComplement` with `strategy` set from the seed's abstracted pattern. `notes` can be left empty — the existing realizer will fill based on strategy.

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/engine/nodes/test_generate_melody_warm_start.py tests/engine/nodes/test_generate_melody.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate_melody.py backend/tests/engine/nodes/test_generate_melody_warm_start.py
git commit -m "feat(m5d): seed melody warm-start strategy per arrangement"
```

---

## Phase 7 — API & session integration

### Task 22: Add `get_pattern_library_repo` dependency

**Files:**
- Modify: `backend/src/explorator/api/deps.py`

- [ ] **Step 1: Add provider**

Edit `backend/src/explorator/api/deps.py`, adding alongside the other repo providers:

```python
from explorator.graph.pattern_library_repo import PatternLibraryRepo


def get_pattern_library_repo(driver: AsyncDriver = Depends(get_neo4j_driver)) -> PatternLibraryRepo:
    return PatternLibraryRepo(driver)
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/explorator/api/deps.py
git commit -m "feat(m5d): add PatternLibraryRepo dependency provider"
```

---

### Task 23: `GET /v1/patterns` — list with filters

**Files:**
- Create: `backend/src/explorator/api/routes/patterns.py`
- Create: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Test**

Create `backend/tests/api/test_patterns_router.py`:

```python
"""Integration tests for the /v1/patterns router."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_patterns_empty(client: AsyncClient):
    resp = await client.get("/v1/patterns")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_list_patterns_filters_by_genre(client: AsyncClient, seed_patterns):
    """seed_patterns fixture inserts 2 house, 1 techno."""
    resp = await client.get("/v1/patterns?genre=house")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(item["genre"] == "house" for item in items)


@pytest.mark.asyncio
async def test_list_patterns_filters_by_pattern_type_and_tags(client: AsyncClient, seed_patterns):
    resp = await client.get("/v1/patterns?genre=house&pattern_type=progression&tags=role:safest")
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["pattern_type"] == "progression"
        assert "role:safest" in item["tags"]
```

(Add a `seed_patterns` fixture in the same file that upserts 3 entries via `PatternLibraryRepo` through the test driver — reuse pattern from `test_genre_research_router.py` if such a test exists, else from `test_feedback_router.py`.)

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: FAIL — router doesn't exist.

- [ ] **Step 3: Implement minimal router**

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


class PatternListResponse(BaseModel):
    items: list[PatternItem]


@router.get("/patterns")
async def list_patterns(
    genre: str | None = None,
    pattern_type: str | None = None,
    tags: str | None = Query(None, description="Comma-separated list of tag filters"),
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternListResponse:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    entries = await repo.list_all(genre=genre, pattern_type=pattern_type, tags=tag_list)
    items = [PatternItem(
        id=e["id"],
        pattern_type=e["pattern_type"],
        genre=e["genre"],
        tags=e.get("tags") or [],
        source_candidate_id=e["source_candidate_id"],
        abstracted_pattern=e.get("abstracted_pattern") or {},
        success_metrics=e.get("success_metrics") or {},
        notes=e.get("notes") or "",
    ) for e in entries]
    return PatternListResponse(items=items)
```

- [ ] **Step 4: Register router**

Edit `backend/src/explorator/api/app.py`. The spec's M5c experience showed route ordering matters — add the patterns router **before** any catch-all `/{id}` patterns but **after** `sessions.router`. Follow the existing registration order exactly as shown in app.py (inserting patterns at the end of the `/v1/` block is the safe choice):

```python
from explorator.api.routes import patterns
...
app.include_router(patterns.router, prefix="/v1")
```

- [ ] **Step 5: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/src/explorator/api/app.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): add GET /v1/patterns with genre/type/tag filters"
```

---

### Task 24: `GET /v1/patterns/{id}` and `DELETE /v1/patterns/{id}`

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Tests**

Append to `backend/tests/api/test_patterns_router.py`:

```python
@pytest.mark.asyncio
async def test_get_pattern_by_id(client, seed_patterns):
    # seed_patterns fixture exposes first pattern id as seed_patterns[0]["id"]
    pid = seed_patterns[0]["id"]
    resp = await client.get(f"/v1/patterns/{pid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pid


@pytest.mark.asyncio
async def test_get_pattern_404(client):
    resp = await client.get("/v1/patterns/pl_does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_pattern(client, seed_patterns):
    pid = seed_patterns[0]["id"]
    resp = await client.delete(f"/v1/patterns/{pid}")
    assert resp.status_code == 204
    resp = await client.get(f"/v1/patterns/{pid}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/api/routes/patterns.py`:

```python
@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternItem:
    entry = await repo.get_by_id(pattern_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return PatternItem(
        id=entry["id"],
        pattern_type=entry["pattern_type"],
        genre=entry["genre"],
        tags=entry.get("tags") or [],
        source_candidate_id=entry["source_candidate_id"],
        abstracted_pattern=entry.get("abstracted_pattern") or {},
        success_metrics=entry.get("success_metrics") or {},
        notes=entry.get("notes") or "",
    )


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

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): add GET and DELETE /v1/patterns/{id}"
```

---

### Task 25: Add `genre` to session creation

**Files:**
- Modify: `backend/src/explorator/api/routes/sessions.py`
- Modify: `backend/tests/api/test_sessions_router.py` (or create)

- [ ] **Step 1: Test**

Add to `backend/tests/api/test_sessions_router.py`:

```python
@pytest.mark.asyncio
async def test_create_session_accepts_genre(client: AsyncClient):
    resp = await client.post("/v1/sessions", json={"mode": "balanced", "prompt": "moody house", "genre": "house"})
    assert resp.status_code == 201
    sid = resp.json()["session_id"]
    detail = await client.get(f"/v1/sessions/{sid}")
    assert detail.status_code == 200
    # genre is round-trippable through session metadata
    assert detail.json().get("genre") == "house"


@pytest.mark.asyncio
async def test_create_session_genre_optional(client: AsyncClient):
    resp = await client.post("/v1/sessions", json={"mode": "balanced", "prompt": "anything goes"})
    assert resp.status_code == 201
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_sessions_router.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Edit sessions.py**

Add `genre: str | None = None` to `CreateSessionRequest`. Add `genre: str | None = None` to `SessionResponse`. In `create_session`, include genre in metadata if provided:

```python
metadata = {"prompt": request.prompt}
if request.genre:
    metadata["genre"] = request.genre
...
    metadata=metadata,
...
return SessionResponse(..., genre=request.genre)
```

In `get_session` and `list_sessions`, read `metadata.get("genre")` and include in responses.

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_sessions_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/sessions.py backend/tests/api/test_sessions_router.py
git commit -m "feat(m5d): accept optional genre on session creation, persist to metadata"
```

---

### Task 26: `GET /v1/sessions/{id}/warm-starts` — fetch suggestions

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Test**

Append:

```python
@pytest.mark.asyncio
async def test_warm_start_suggestions_grouped_by_pattern_type(client, seeded_house_session, seed_patterns):
    """GET /sessions/{id}/warm-starts returns patterns grouped by pattern_type for the session's genre."""
    resp = await client.get(f"/v1/sessions/{seeded_house_session['session_id']}/warm-starts")
    assert resp.status_code == 200
    body = resp.json()
    assert "suggestions" in body
    assert "progression" in body["suggestions"]
    assert all(p["genre"] == "house" for p in body["suggestions"]["progression"])


@pytest.mark.asyncio
async def test_warm_start_suggestions_empty_for_session_with_no_genre(client):
    """If the session lacks a genre, suggestions is {}."""
    # create a session without genre
    sr = await client.post("/v1/sessions", json={"mode": "balanced", "prompt": "plain"})
    sid = sr.json()["session_id"]
    resp = await client.get(f"/v1/sessions/{sid}/warm-starts")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == {}
```

(Add `seeded_house_session` fixture that creates a session with `genre=house`.)

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: new tests FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/api/routes/patterns.py`:

```python
from neo4j import AsyncDriver
from explorator.api.deps import get_neo4j_driver, get_session_repo
from explorator.graph.session_repo import SessionRepository
from explorator.services.pattern_retrieval import GraphRetrieval
from explorator.utils import parse_json_or_dict


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
    metadata = parse_json_or_dict(session.get("metadata"))
    genre = metadata.get("genre")
    if not genre:
        return WarmStartSuggestions(suggestions={})

    retrieval = GraphRetrieval(repo=pattern_repo)
    grouped = await retrieval.fetch(genre=genre, top_k_per_type=top_k_per_type)
    return WarmStartSuggestions(suggestions={
        ptype: [PatternItem(
            id=e["id"],
            pattern_type=e["pattern_type"],
            genre=e["genre"],
            tags=e.get("tags") or [],
            source_candidate_id=e["source_candidate_id"],
            abstracted_pattern=e.get("abstracted_pattern") or {},
            success_metrics=e.get("success_metrics") or {},
            notes=e.get("notes") or "",
        ) for e in entries]
        for ptype, entries in grouped.items()
    })
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): GET /v1/sessions/{id}/warm-starts returns pattern suggestions by genre"
```

---

### Task 27: `POST /v1/sessions/{id}/warm-starts` — save selections

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`
- Modify: `backend/src/explorator/graph/session_repo.py` — add `update_metadata` helper if not present

- [ ] **Step 1: Test**

Append:

```python
@pytest.mark.asyncio
async def test_post_warm_starts_persists_selected_pattern_ids(client, seeded_house_session, seed_patterns):
    sid = seeded_house_session["session_id"]
    pattern_ids = [seed_patterns[0]["id"]]

    resp = await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": pattern_ids})
    assert resp.status_code == 200
    assert resp.json() == {"pattern_ids": pattern_ids}

    detail = await client.get(f"/v1/sessions/{sid}")
    # Round-trip exposure through session detail
    assert detail.json().get("warm_start_pattern_ids") == pattern_ids


@pytest.mark.asyncio
async def test_post_warm_starts_rejects_nonexistent_patterns(client, seeded_house_session):
    sid = seeded_house_session["session_id"]
    resp = await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": ["pl_ghost"]})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/api/routes/patterns.py`:

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

    # Validate every pattern_id exists
    for pid in request.pattern_ids:
        if await pattern_repo.get_by_id(pid) is None:
            raise HTTPException(status_code=400, detail=f"Pattern not found: {pid}")

    # Merge into session metadata
    metadata = parse_json_or_dict(session.get("metadata"))
    metadata["warm_start_pattern_ids"] = request.pattern_ids

    async with driver.session() as neo_session:
        await neo_session.run(
            "MATCH (s:Session {id: $sid}) SET s.metadata = $metadata",
            sid=session_id,
            metadata=__import__("json").dumps(metadata),
        )

    return SetWarmStartsResponse(pattern_ids=request.pattern_ids)
```

Also update `SessionResponse` in `sessions.py` to include `warm_start_pattern_ids: list[str] = []` and populate from metadata in `get_session`/`list_sessions`.

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py tests/api/test_sessions_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/src/explorator/api/routes/sessions.py backend/tests/api/test_patterns_router.py backend/tests/api/test_sessions_router.py
git commit -m "feat(m5d): POST /v1/sessions/{id}/warm-starts persists selections to session metadata"
```

---

### Task 28: `rounds.py` reads warm-starts from session into `initial_state`

**Files:**
- Modify: `backend/src/explorator/api/routes/rounds.py`
- Modify: `backend/tests/api/test_rounds_router.py` (or create)

- [ ] **Step 1: Test**

Append to (or create) `backend/tests/api/test_rounds_router.py`:

```python
@pytest.mark.asyncio
async def test_trigger_round_passes_warm_start_ids_from_session_metadata(client, monkeypatch, seeded_house_session, seed_patterns):
    """When rounds start, initial_state should contain warm_start_pattern_ids from session metadata."""
    captured_states = []

    class _FakeGraph:
        async def ainvoke(self, state, _cfg):
            captured_states.append(state)
            return state

    def _build(_g, _d):
        return _FakeGraph()

    monkeypatch.setattr("explorator.api.routes.rounds.build_exploration_graph", _build)

    # Set warm-starts
    sid = seeded_house_session["session_id"]
    await client.post(f"/v1/sessions/{sid}/warm-starts", json={"pattern_ids": [seed_patterns[0]["id"]]})

    # Trigger a round
    async with client.stream("POST", f"/v1/sessions/{sid}/rounds", json={"generation_mode": "balanced"}) as r:
        async for _ in r.aiter_lines():
            break  # bail after first event so background task gets to run

    # Allow the background task to capture
    import asyncio
    await asyncio.sleep(0.1)

    assert captured_states, "graph was not invoked"
    state = captured_states[0]
    assert state.get("warm_start_pattern_ids") == [seed_patterns[0]["id"]]
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_rounds_router.py -v`
Expected: FAIL.

- [ ] **Step 3: Edit `rounds.py`**

Add `warm_start_pattern_ids = metadata.get("warm_start_pattern_ids") or []` next to `session_prompt`. Add to `initial_state`:

```python
"warm_start_pattern_ids": warm_start_pattern_ids,
```

Also add genre passthrough:
```python
"genre": metadata.get("genre", ""),
```

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_rounds_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/rounds.py backend/tests/api/test_rounds_router.py
git commit -m "feat(m5d): rounds.py injects warm_start_pattern_ids + genre into initial_state"
```

---

### Task 29: `POST /v1/sessions/{id}/finalists/harvest` — manual re-save

**Files:**
- Modify: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 1: Test**

Append:

```python
@pytest.mark.asyncio
async def test_harvest_finalists_endpoint_persists_patterns_from_persisted_arrangements(client, completed_session):
    """Manual harvest endpoint idempotently upserts pattern entries for the session's finalists."""
    sid = completed_session["session_id"]
    resp = await client.post(f"/v1/sessions/{sid}/finalists/harvest")
    assert resp.status_code == 200
    count_1 = resp.json()["harvested_count"]
    assert count_1 > 0

    # Second call is idempotent
    resp2 = await client.post(f"/v1/sessions/{sid}/finalists/harvest")
    assert resp2.json()["harvested_count"] == count_1
```

(`completed_session` fixture runs a full session to `final_selection`, or inserts synthetic candidates + scorecards + final_selection into Neo4j — copy pattern from `test_export_router.py`.)

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/api/routes/patterns.py`:

```python
from explorator.services.pattern_harvesting import harvest_finalist
from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.progression_candidate_repo import ProgressionCandidateRepo
from explorator.graph.voicing_plan_repo import VoicingPlanRepo
from explorator.graph.bass_line_repo import BassLineRepo
from explorator.graph.groove_pattern_repo import GroovePatternRepo
from explorator.graph.melodic_complement_repo import MelodicComplementRepo
from explorator.graph.scorecard_repo import ScorecardRepo
from explorator.graph.final_selection_repo import FinalSelectionRepo


class HarvestFinalistsResponse(BaseModel):
    harvested_count: int
    pattern_ids: list[str]


@router.post("/sessions/{session_id}/finalists/harvest")
async def harvest_finalists(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
    pattern_repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> HarvestFinalistsResponse:
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    metadata = parse_json_or_dict(session.get("metadata"))
    genre = metadata.get("genre", "unknown")

    # Load finalists for this session
    final_repo = FinalSelectionRepo(driver)
    final = await final_repo.get_latest_for_session(session_id)
    if final is None or not final.get("selected_candidate_ids"):
        return HarvestFinalistsResponse(harvested_count=0, pattern_ids=[])

    arr_repo = ArrangementCandidateRepo(driver)
    prog_repo = ProgressionCandidateRepo(driver)
    vp_repo = VoicingPlanRepo(driver)
    bl_repo = BassLineRepo(driver)
    gp_repo = GroovePatternRepo(driver)
    mc_repo = MelodicComplementRepo(driver)
    sc_repo = ScorecardRepo(driver)

    roles = final.get("selection_roles") or {}
    harvested: list[str] = []
    for arr_id in final["selected_candidate_ids"]:
        arrangement = await arr_repo.get_by_id(arr_id)
        if arrangement is None:
            continue
        progression = await prog_repo.get_by_id(arrangement.get("progression_candidate_id"))
        if progression is None:
            continue
        vp = await vp_repo.get_by_id(arrangement.get("voicing_plan_id")) if arrangement.get("voicing_plan_id") else None
        bl = await bl_repo.get_by_id(arrangement.get("bass_line_id")) if arrangement.get("bass_line_id") else None
        gp = await gp_repo.get_by_id(arrangement.get("groove_pattern_id")) if arrangement.get("groove_pattern_id") else None
        mc = await mc_repo.get_by_id(arrangement.get("melodic_complement_id")) if arrangement.get("melodic_complement_id") else None
        scorecard = await sc_repo.get_by_candidate_id(arr_id) or {"weighted_total": 0.0, "scores": {}, "pareto_tags": []}

        entries = harvest_finalist(
            arrangement=arrangement,
            progression=progression,
            voicing_plan=vp,
            bass_line=bl,
            groove=gp,
            melody=mc,
            scorecard=scorecard,
            genre=genre,
            role=roles.get(arr_id, "unknown"),
        )
        for entry in entries:
            # Idempotence: if a pattern exists with same (source_candidate_id, pattern_type), skip
            existing = await pattern_repo.list_all(pattern_type=entry.pattern_type)
            if any(e["source_candidate_id"] == entry.source_candidate_id for e in existing):
                continue
            await pattern_repo.upsert(entry)
            harvested.append(entry.id)

    return HarvestFinalistsResponse(harvested_count=len(harvested), pattern_ids=harvested)
```

**Note:** Some of the repo imports above may not exist under those exact names. Before running the test, grep the repo directory (`ls backend/src/explorator/graph/`) and adjust imports to match actual filenames (e.g. `groove_repo.py` vs `groove_pattern_repo.py`). Replace placeholder imports with actual ones. The logic shape is unchanged.

- [ ] **Step 4: Run**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/api/routes/patterns.py backend/tests/api/test_patterns_router.py
git commit -m "feat(m5d): POST /v1/sessions/{id}/finalists/harvest for manual re-save"
```

---

## Phase 8 — Frontend: dependency, API client, store

### Task 30: Install Sonner and mount `<Toaster />`

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/toastWrapper.ts`

- [ ] **Step 1: Install**

Run: `cd frontend && npm install sonner`

Expected: `sonner` appears in `package.json` dependencies.

- [ ] **Step 2: Create wrapper**

Create `frontend/src/components/toastWrapper.ts`:

```ts
import { toast } from 'sonner';

export const toastSuccess = (message: string) => toast.success(message);
export const toastError = (message: string) => toast.error(message);
export const toastInfo = (message: string) => toast(message);
```

- [ ] **Step 3: Mount Toaster**

Edit `frontend/src/App.tsx`:

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

(The `PatternLibraryBrowser` import will fail TypeScript compile until Task 34; that's fine — we'll fix by creating a stub in this task.)

Create a stub `frontend/src/components/PatternLibraryBrowser.tsx`:

```tsx
export default function PatternLibraryBrowser() {
  return <div>Pattern Library (coming in Task 34)</div>;
}
```

- [ ] **Step 4: Smoke-check type-check**

Run: `cd frontend && npm run build` (or `tsc --noEmit` if the script exists)
Expected: no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/App.tsx frontend/src/components/toastWrapper.ts frontend/src/components/PatternLibraryBrowser.tsx
git commit -m "feat(m5d): add Sonner toaster, /patterns route, toast wrapper"
```

---

### Task 31: Add pattern API client functions

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Read existing `api.ts`**

Read the file to find the pattern for existing calls (URL base, method signatures).

- [ ] **Step 2: Add pattern API functions**

Append to `frontend/src/services/api.ts`:

```ts
export interface PatternItem {
  id: string;
  pattern_type: 'progression' | 'voicing' | 'bass' | 'groove' | 'melody';
  genre: string;
  tags: string[];
  source_candidate_id: string;
  abstracted_pattern: Record<string, unknown>;
  success_metrics: Record<string, number>;
  notes: string;
}

export async function listPatterns(filters: { genre?: string; pattern_type?: string; tags?: string[] } = {}): Promise<PatternItem[]> {
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

(Use `API_BASE` — or whatever constant the file already defines. Read first.)

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat(m5d): add pattern library API client functions"
```

---

### Task 32: Create `patternLibraryStore` (Zustand)

**Files:**
- Create: `frontend/src/stores/patternLibraryStore.ts`
- Create: `frontend/src/stores/__tests__/patternLibraryStore.test.ts`

- [ ] **Step 1: Write failing test**

Create `frontend/src/stores/__tests__/patternLibraryStore.test.ts`:

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

  it('loads patterns by genre', async () => {
    const mockItems = [{ id: 'pl_1', pattern_type: 'progression', genre: 'house', tags: [], source_candidate_id: 'arr_1', abstracted_pattern: {}, success_metrics: {}, notes: '' } as api.PatternItem];
    vi.mocked(api.listPatterns).mockResolvedValue(mockItems);

    await usePatternLibraryStore.getState().fetchPatterns({ genre: 'house' });

    expect(usePatternLibraryStore.getState().patterns).toEqual(mockItems);
    expect(api.listPatterns).toHaveBeenCalledWith({ genre: 'house' });
  });

  it('tracks selected pattern ids for warm starts', () => {
    const store = usePatternLibraryStore.getState();
    store.toggleSelection('pl_1');
    store.toggleSelection('pl_2');
    expect(usePatternLibraryStore.getState().selectedPatternIds).toEqual(['pl_1', 'pl_2']);
    store.toggleSelection('pl_1');
    expect(usePatternLibraryStore.getState().selectedPatternIds).toEqual(['pl_2']);
  });

  it('clears selections on reset', () => {
    const store = usePatternLibraryStore.getState();
    store.toggleSelection('pl_1');
    store.reset();
    expect(usePatternLibraryStore.getState().selectedPatternIds).toEqual([]);
  });
});
```

- [ ] **Step 2: Run**

Run: `cd frontend && npx vitest run src/stores/__tests__/patternLibraryStore.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `frontend/src/stores/patternLibraryStore.ts`:

```ts
import { create } from 'zustand';
import { listPatterns, deletePattern, PatternItem } from '../services/api';

interface PatternLibraryState {
  patterns: PatternItem[];
  loading: boolean;
  error: string | null;
  selectedPatternIds: string[];
  activeFilter: { genre?: string; pattern_type?: string; tags?: string[] };

  fetchPatterns: (filters: { genre?: string; pattern_type?: string; tags?: string[] }) => Promise<void>;
  toggleSelection: (id: string) => void;
  clearSelection: () => void;
  removePattern: (id: string) => Promise<void>;
  reset: () => void;
}

export const usePatternLibraryStore = create<PatternLibraryState>((set, get) => ({
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
    } catch (err) {
      set({ loading: false, error: (err as Error).message });
    }
  },

  toggleSelection: (id) => {
    const current = get().selectedPatternIds;
    set({
      selectedPatternIds: current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id],
    });
  },

  clearSelection: () => set({ selectedPatternIds: [] }),

  removePattern: async (id) => {
    await deletePattern(id);
    set({ patterns: get().patterns.filter((p) => p.id !== id) });
  },

  reset: () => set({ patterns: [], loading: false, error: null, selectedPatternIds: [], activeFilter: {} }),
}));
```

- [ ] **Step 4: Run**

Run: `cd frontend && npx vitest run src/stores/__tests__/patternLibraryStore.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/patternLibraryStore.ts frontend/src/stores/__tests__/patternLibraryStore.test.ts
git commit -m "feat(m5d): add patternLibraryStore with fetch, selection, delete"
```

---

### Task 33: `WarmStartPanel` component

**Files:**
- Create: `frontend/src/components/WarmStartPanel.tsx`

- [ ] **Step 1: Implement component**

Create `frontend/src/components/WarmStartPanel.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { listPatterns, PatternItem } from '../services/api';

interface WarmStartPanelProps {
  genre: string;
  selectedIds: string[];
  onToggle: (id: string) => void;
  onStartFresh: () => void;
}

const TYPE_ORDER: PatternItem['pattern_type'][] = ['progression', 'voicing', 'bass', 'groove', 'melody'];

export default function WarmStartPanel({ genre, selectedIds, onToggle, onStartFresh }: WarmStartPanelProps) {
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
  if (!patterns || patterns.length === 0) return null;  // Graceful absence per spec §5.5

  const grouped = TYPE_ORDER.map((ptype) => ({
    ptype,
    items: patterns.filter((p) => p.pattern_type === ptype),
  })).filter((g) => g.items.length > 0);

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
      <button type="button" onClick={onStartFresh} data-testid="start-fresh-btn">Start fresh (skip warm start)</button>
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WarmStartPanel.tsx
git commit -m "feat(m5d): add WarmStartPanel component"
```

---

### Task 34: `PatternLibraryBrowser` component

**Files:**
- Modify: `frontend/src/components/PatternLibraryBrowser.tsx` (replace stub)

- [ ] **Step 1: Replace stub with real implementation**

Overwrite `frontend/src/components/PatternLibraryBrowser.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePatternLibraryStore } from '../stores/patternLibraryStore';
import { toastSuccess, toastError } from './toastWrapper';

export default function PatternLibraryBrowser() {
  const navigate = useNavigate();
  const { patterns, loading, fetchPatterns, removePattern } = usePatternLibraryStore();
  const [genreFilter, setGenreFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  useEffect(() => {
    fetchPatterns({
      genre: genreFilter || undefined,
      pattern_type: typeFilter || undefined,
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
          <option value="progression">progression</option>
          <option value="voicing">voicing</option>
          <option value="bass">bass</option>
          <option value="groove">groove</option>
          <option value="melody">melody</option>
        </select>
      </div>
      {loading && <p>Loading…</p>}
      {!loading && patterns.length === 0 && <p data-testid="empty-library">No patterns yet. They'll appear here after a session reaches finalist selection.</p>}
      <ul>
        {patterns.map((p) => (
          <li key={p.id} data-testid={`pattern-row-${p.id}`}>
            <span className="type">{p.pattern_type}</span>
            <span className="genre">{p.genre}</span>
            <span className="tags">{p.tags.join(', ')}</span>
            <span className="score">{(p.success_metrics.weighted_total ?? 0).toFixed(2)}</span>
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

- [ ] **Step 2: Type-check and smoke-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

Run: `cd frontend && npm run dev` in one terminal; open `http://0.0.0.0:5173/patterns`.
Expected: empty library message (if no patterns seeded) or list of patterns.

Stop the dev server.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PatternLibraryBrowser.tsx
git commit -m "feat(m5d): implement PatternLibraryBrowser with filters + delete"
```

---

### Task 35: Wire `WarmStartPanel` into Dashboard session creation

**Files:**
- Modify: `frontend/src/views/Dashboard.tsx`

- [ ] **Step 1: Read current Dashboard**

Read `frontend/src/views/Dashboard.tsx` — understand the existing session-creation flow (genre selector? prompt input? submit handler?).

- [ ] **Step 2: Add genre selector + warm-start panel**

Modify `frontend/src/views/Dashboard.tsx` so:

1. The form accepts (or already accepts) a `genre` value via a `<select>`. Options come from `listGenres()` (existing API call; reuse if already wired).
2. After a genre is picked, render `<WarmStartPanel>`.
3. Track `selectedPatternIds` in local state or via `usePatternLibraryStore`.
4. On submit, include `genre` and (if warm-starts selected) pass `selectedPatternIds` into a new method: call `createSession({ prompt, genre })` → `setWarmStarts(sessionId, selectedPatternIds)` → `navigate(/session/:id)`.
5. Add a nav link/button to `/patterns` in the header for browsing the library.

Key code addition:

```tsx
import WarmStartPanel from '../components/WarmStartPanel';
import { createSession, setWarmStarts } from '../services/api';
import { toastInfo } from '../components/toastWrapper';
...
const [genre, setGenre] = useState('');
const [selectedPatternIds, setSelectedPatternIds] = useState<string[]>([]);
...
const handleSubmit = async () => {
  const { session_id } = await createSession({ prompt, genre, mode });
  if (selectedPatternIds.length > 0) {
    await setWarmStarts(session_id, selectedPatternIds);
    toastInfo(`${selectedPatternIds.length} warm-starts applied.`);
  }
  navigate(`/session/${session_id}`);
};
```

And in JSX:
```tsx
<select value={genre} onChange={(e) => setGenre(e.target.value)} data-testid="dashboard-genre">
  <option value="">Pick a genre…</option>
  {availableGenres.map((g) => <option key={g} value={g}>{g}</option>)}
</select>
{genre && (
  <WarmStartPanel
    genre={genre}
    selectedIds={selectedPatternIds}
    onToggle={(id) => setSelectedPatternIds((ids) => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])}
    onStartFresh={() => setSelectedPatternIds([])}
  />
)}
<Link to="/patterns" data-testid="dashboard-patterns-link">Pattern Library</Link>
```

- [ ] **Step 3: Smoke-check**

Run: `cd frontend && npm run dev`. Create a session, pick a genre. If patterns exist for that genre, the panel should render. "Start Fresh" clears selections.

Stop dev server.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Dashboard.tsx
git commit -m "feat(m5d): wire WarmStartPanel into Dashboard session creation flow"
```

---

### Task 36: Harvest toast + `Save to library` button in `FinalistPanel`

**Files:**
- Modify: `frontend/src/components/FinalistPanel.tsx`
- Modify: `frontend/src/components/SessionWorkspace.tsx` (add SSE handler)

- [ ] **Step 1: Add button to FinalistPanel**

Read `frontend/src/components/FinalistPanel.tsx`, then add at the top of the component's return:

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
<button type="button" onClick={handleSaveToLibrary} data-testid="save-to-library-btn">
  Save finalists to library
</button>
```

(Ensure `sessionId` is already a prop or is accessible via route params.)

- [ ] **Step 2: Add SSE handler for auto-harvest notification**

Read `frontend/src/components/SessionWorkspace.tsx`. Find where SSE events from `/sessions/{id}/rounds` are processed. Add a branch for `pattern_harvest`:

```ts
import { toastSuccess } from './toastWrapper';
...
if (event.type === 'pattern_harvest') {
  const { count, genre } = JSON.parse(event.data);
  toastSuccess(`${count} ${genre} pattern${count === 1 ? '' : 's'} saved to library`);
}
```

(Match the file's existing SSE dispatch shape.)

- [ ] **Step 3: Smoke-check**

Run a full session in the dev server and verify the toast appears. Click "Save finalists to library" — verify it's idempotent.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/FinalistPanel.tsx frontend/src/components/SessionWorkspace.tsx
git commit -m "feat(m5d): save-to-library button + auto-harvest toast in session workspace"
```

---

## Phase 9 — E2E tests

### Task 37: E2E harness + "harvest after finalist selection" test

**Files:**
- Create: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Write test**

Create `e2e/tests/warm-starts.spec.ts`:

```ts
import { test, expect } from '@playwright/test';
import { runFullSession } from '../fixtures/session';

test.describe('M5d — Retrieval-Assisted Warm Starts', () => {
  test('patterns are harvested automatically after finalist selection', async ({ page, request }) => {
    // Start with empty library
    const before = await request.get('/v1/patterns?genre=house');
    const beforeCount = (await before.json()).items.length;

    // Run a full house session to completion
    await runFullSession(page, { genre: 'house', prompt: 'bouncy house groove' });

    // After session completes, library should have new entries for this genre
    const after = await request.get('/v1/patterns?genre=house');
    const afterCount = (await after.json()).items.length;
    expect(afterCount).toBeGreaterThan(beforeCount);
  });
});
```

The `runFullSession` fixture is new — create it:

Create `e2e/fixtures/session.ts` (if not already present; extend if it is):

```ts
import { Page, expect } from '@playwright/test';

interface SessionOptions {
  genre: string;
  prompt: string;
}

export async function runFullSession(page: Page, { genre, prompt }: SessionOptions) {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', genre);
  await page.fill('[data-testid=dashboard-prompt]', prompt);  // adjust to match real test-id
  await page.click('[data-testid=dashboard-submit]');
  // Wait for session page
  await page.waitForURL(/\/session\/sess_/);
  // Wait for FinalistPanel to render
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 120_000 });
}
```

- [ ] **Step 2: Run**

Run: `cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium`
Expected: PASS (assuming the existing Neo4j test instance is clean and backend is running per `global-setup.ts`).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/warm-starts.spec.ts e2e/fixtures/session.ts
git commit -m "test(m5d): e2e test for automatic pattern harvest"
```

---

### Task 38: E2E test — pattern appears in library browser

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Add test**

Append to `e2e/tests/warm-starts.spec.ts`:

```ts
test('harvested pattern appears in library browser with correct tags', async ({ page }) => {
  await runFullSession(page, { genre: 'house', prompt: 'warm-start source run' });
  await page.goto('/patterns');
  await expect(page.locator('[data-testid=pattern-library-browser]')).toBeVisible();
  await page.fill('[data-testid=filter-genre]', 'house');
  const rows = page.locator('[data-testid^=pattern-row-]');
  await expect(rows).not.toHaveCount(0);
  // At least one progression entry with a role tag
  await expect(rows.filter({ hasText: 'progression' }).first()).toContainText(/role:(safest|best_loop|most_experimental)/);
});
```

- [ ] **Step 2: Run**

Run: `cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e verify pattern browser shows harvested entry with role tag"
```

---

### Task 39: E2E test — warm-start panel appears + seeds generation

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Add test**

Append:

```ts
test('warm-start panel appears on dashboard when patterns exist for chosen genre', async ({ page }) => {
  // Precondition: Task 37's test has already populated the library.
  // Run a fresh session and verify the panel renders.
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible({ timeout: 10_000 });
  const toggles = page.locator('[data-testid^=warm-start-toggle-]');
  await expect(toggles).not.toHaveCount(0);
});


test('warm-start seeds round-1 generation with the selected pattern', async ({ page, request }) => {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible();
  // Pick the first available pattern
  const firstToggle = page.locator('[data-testid^=warm-start-toggle-]').first();
  const toggleId = await firstToggle.getAttribute('data-testid');
  const patternId = toggleId!.replace('warm-start-toggle-', '');
  await firstToggle.check();
  await page.fill('[data-testid=dashboard-prompt]', 'seeded session');
  await page.click('[data-testid=dashboard-submit]');
  await page.waitForURL(/\/session\/sess_/);
  const sessionId = page.url().split('/').pop()!;
  // Wait for any progression cards to render
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 120_000 });
  // Verify at least one candidate has warm_start_pattern_id == patternId via API
  const resp = await request.get(`/v1/sessions/${sessionId}/candidates`);
  const body = await resp.json();
  const hasSeededCandidate = body.items.some((c: { metadata?: { warm_start_pattern_id?: string } }) => c.metadata?.warm_start_pattern_id === patternId);
  expect(hasSeededCandidate).toBe(true);
});
```

- [ ] **Step 2: Run**

Run: `cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e warm-start panel and seeding"
```

---

### Task 40: E2E test — "start fresh" skips warm start

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Add test**

Append:

```ts
test('start-fresh button clears selections and skips warm start', async ({ page, request }) => {
  await page.goto('/');
  await page.selectOption('[data-testid=dashboard-genre]', 'house');
  await expect(page.locator('[data-testid=warm-start-panel]')).toBeVisible();
  await page.locator('[data-testid^=warm-start-toggle-]').first().check();
  await page.click('[data-testid=start-fresh-btn]');
  // All toggles should be unchecked
  const checked = await page.locator('[data-testid^=warm-start-toggle-]:checked').count();
  expect(checked).toBe(0);
  // Create the session; verify no candidate carries a warm_start_pattern_id
  await page.fill('[data-testid=dashboard-prompt]', 'fresh');
  await page.click('[data-testid=dashboard-submit]');
  await page.waitForURL(/\/session\/sess_/);
  const sessionId = page.url().split('/').pop()!;
  await expect(page.locator('[data-testid=finalist-panel]')).toBeVisible({ timeout: 120_000 });
  const resp = await request.get(`/v1/sessions/${sessionId}/candidates`);
  const body = await resp.json();
  expect(body.items.every((c: { metadata?: { warm_start_pattern_id?: string } }) => !c.metadata?.warm_start_pattern_id)).toBe(true);
});
```

- [ ] **Step 2: Run**

Run: `cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e start-fresh skips warm start"
```

---

### Task 41: E2E test — pattern deletion

**Files:**
- Modify: `e2e/tests/warm-starts.spec.ts`

- [ ] **Step 1: Add test**

Append:

```ts
test('pattern can be deleted from the library browser', async ({ page, request }) => {
  // Ensure at least one pattern exists
  const list = await (await request.get('/v1/patterns?genre=house')).json();
  expect(list.items.length).toBeGreaterThan(0);
  const victim = list.items[0];

  await page.goto('/patterns');
  await page.fill('[data-testid=filter-genre]', 'house');
  const row = page.locator(`[data-testid=pattern-row-${victim.id}]`);
  await expect(row).toBeVisible();
  await row.locator(`[data-testid=delete-pattern-${victim.id}]`).click();
  await expect(row).toHaveCount(0, { timeout: 5_000 });

  // Verify API no longer returns it
  const after = await (await request.get(`/v1/patterns/${victim.id}`)).status();
  expect(after).toBe(404);
});
```

- [ ] **Step 2: Run**

Run: `cd e2e && npx playwright test tests/warm-starts.spec.ts --project=chromium`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/warm-starts.spec.ts
git commit -m "test(m5d): e2e pattern deletion from library browser"
```

---

## Phase 10 — Integration polish

### Task 42: Full regression sweep + end-to-end smoke

**Files:** (no file changes — verification only)

- [ ] **Step 1: Backend full suite**

Run: `cd backend && uv run pytest -v`
Expected: all tests PASS; no regressions from any earlier milestone. Verify count is ≥ 492 (M5b baseline) + new M5d tests.

- [ ] **Step 2: Frontend full suite**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run build`
Expected: tests PASS; tsc clean; build succeeds.

- [ ] **Step 3: E2E full suite**

Run: `cd e2e && npx playwright test --project=chromium`
Expected: all existing tests PASS, plus 5 new warm-start tests from Tasks 37-41.

- [ ] **Step 4: Manual smoke** — run the full end-to-end flow in the dev environment:
  1. Start backend (`uv run uvicorn explorator.api.app:app --host 0.0.0.0 --port 8000`)
  2. Start frontend (`cd frontend && npm run dev`)
  3. Open http://0.0.0.0:5173/
  4. Create a new house session — verify that no warm-start panel appears (empty library).
  5. Let the session run to finalist selection — verify the SSE toast "N patterns saved to library".
  6. Click "Save finalists to library" button — verify idempotent toast "Finalists already saved to library".
  7. Navigate to `/patterns` — verify the harvested entries show with correct tags.
  8. Return to `/` and create a second house session — verify WarmStartPanel now appears with the harvested patterns.
  9. Select one progression warm-start + one groove warm-start; submit.
  10. On the session page, verify at least one progression candidate and one groove pattern have `warm_start_pattern_id` in their metadata (check via `/v1/sessions/{id}/candidates` or visible in UI if exposed).
  11. Delete one pattern from `/patterns` — verify it disappears and the API returns 404.

- [ ] **Step 5: Commit final tidy-up if any**

If the manual smoke surfaced small issues (copy text, missing test-ids, etc.), fix them and:

```bash
git add -u
git commit -m "chore(m5d): manual-smoke polish"
```

Otherwise skip.

---

## Self-Review Checklist

Before handing off, confirm:

1. **Spec coverage:**
   - §5.2 Pattern Harvesting — Tasks 5-13 (harvesting + auto node + wiring) ✓
   - §5.3 Retrieval — Tasks 14-16 (GraphRetrieval + load_warm_starts + wiring) ✓
   - §5.4 Backend API — Tasks 22-29 (GET/DELETE/{id}, warm-starts GET/POST, harvest) ✓
   - §5.5 Warm Start Integration — Tasks 17-21 (five generation-node integrations) ✓
   - §5.6 Frontend — Tasks 30-36 (Sonner, store, WarmStartPanel, Browser, Dashboard wiring, FinalistPanel button, SSE toast) ✓
   - §5.7 E2E Tests — Tasks 37-41 (5 tests; matches spec's "5-6 new") ✓

2. **Placeholder scan:** No TBDs, TODOs, or "implement later." Every step has concrete code or a read-file-then-adapt instruction with enough specificity for an engineer to act without re-interpreting the spec.

3. **Type consistency:**
   - `PatternLibraryEntry` field shape matches across models, repo, harvesting service, API responses, and frontend `PatternItem` interface.
   - Method names (`upsert`, `get_by_id`, `list_all`, `query_for_warm_starts`, `delete_by_id`) are consistent in repo definition and test usage.
   - `harvest_finalist` parameter names match across definition, callers (`harvest_patterns` node, `harvest_finalists` router), and tests.
   - Warm-start metadata flag name (`warm_start_pattern_id`) is identical in every generation node and in every test assertion.

4. **Vector-readiness:** `embedding: list[float] | None = None` is present on the model; `GraphRetrieval` is exposed as one implementation of a `RetrievalStrategy` Protocol so swapping to `VectorRetrieval` later needs no caller changes.

---

## Execution handoff

Plan is ready. Tasks 1-41 are ordered so that each task commits independently and leaves the tree in a green state (tests pass, tsc clean).

Task counts: **41 implementation tasks + 1 integration-sweep task** spread across 10 phases.

Risk areas worth flagging to reviewer as the plan executes:
- Tasks 17-21 (warm-start injection) require reading the existing node implementations first; the plan deliberately stops short of dictating the exact file diff because those nodes have varying internal structures (some call Gemini directly, some are deterministic, some operate on top_progressions vs. arrangement_candidates).
- Task 29 depends on repo modules whose exact names may differ from the imports shown — verify by `ls backend/src/explorator/graph/` before running the test.
- Task 36's SSE dispatch shape in `SessionWorkspace.tsx` must be matched to the file's existing event-handling pattern (inspect `genre_research` or `rounds` SSE handling for reference).
