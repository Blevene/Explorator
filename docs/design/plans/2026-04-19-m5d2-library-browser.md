# M5d-2 Pattern Library Browser Implementation Plan


**Goal:** Add a pattern library browser (read/delete UI + HTTP API), harvest feedback toasts, and a manual re-save endpoint — making M5d-1's silently-harvested patterns visible and curatable.

**Architecture:** Two commits. Commit A is a pure refactor: extract M5d-1's `harvest_patterns` node body into a transport-free helper (`harvest_session_finalists_from_state`) with a typed `HarvestReport` return, no external behavior change. Commit B builds the API + frontend on top: new `/v1/patterns` router (list/get/delete) with keyset pagination and a plaintext cursor, a `POST /v1/sessions/{id}/finalists/harvest` manual re-save endpoint, a soft-delete `deleted_at` column with MERGE-resurrection, a `/patterns` React route with two Zustand stores, Sonner toasts, and a "Save finalists to library" button on `FinalistPanel`.

**Tech Stack:** Backend: Python 3.12 / FastAPI / Neo4j via `neo4j` async driver / Pydantic / pytest (run with `uv run pytest`). Frontend: React + TypeScript + Vite / Zustand / React Router v7 / Sonner / Vitest (run with `npm run test:unit`). E2E: Playwright.

**Spec:** `docs/design/specs/2026-04-19-m5d2-library-browser-design.md` (commits 825e4c2 + c52fdb8).

---

## Preflight: regression-guard audit (no code change)

The spec mandates an audit of `backend/tests/integration/test_m5d1_harvest.py` before Commit A: confirm assertions are field-subset / attribute-wise rather than exhaustive dict or dataclass equality, so Commit A's helper extraction (and any internal type shape) doesn't fail the regression guard.

**Audit result (pre-verified):** The file uses only `len()`, specific key lookups (`result["harvested_pattern_ids"]`), and tuple-equality on individual progress-event args. No exhaustive dict/dataclass equality. **No precursor commit needed.** The node wrapper in Task 3 preserves the exact external contract (`{"harvested_pattern_ids": ...}` return dict + three progress-event shapes).

**Note:** The `harvest_patterns` node currently emits an extra `pattern_harvest` domain event on the happy path. This must also be preserved in Task 3.

---

# Commit A — Pure extraction (no behavior change)

## Task 1: Scaffold `services/pattern_library` package and HarvestReport types

**Files:**
- Create: `backend/src/explorator/services/__init__.py` (if it doesn't already exist)
- Create: `backend/src/explorator/services/pattern_library/__init__.py`
- Create: `backend/src/explorator/services/pattern_library/harvest_service.py`

- [ ] **Step 1.1: Check if `services/` exists**

Run: `ls backend/src/explorator/services/ 2>&1`
If missing, create the directory and a stub `__init__.py` with the content:

```python
"""Service-layer orchestration modules that compose multiple repositories."""
```

- [ ] **Step 1.2: Create `services/pattern_library/__init__.py`**

```python
"""Pattern library service: harvest orchestration, keyset cursor, soft-delete."""
```

- [ ] **Step 1.3: Create the harvest service module (types only; helper stub comes in Task 2)**

Write `backend/src/explorator/services/pattern_library/harvest_service.py`:

```python
"""Transport-free pattern harvest orchestration.

Extracted from the LangGraph `harvest_patterns` node so the same logic can be
reused by the POST /v1/sessions/{id}/finalists/harvest API endpoint.
"""
from dataclasses import dataclass, field
from enum import Enum


class SkipReason(str, Enum):
    """Why a candidate facet was not upserted to the library."""
    MISSING_ARRANGEMENT = "missing_arrangement"
    MISSING_PROGRESSION = "missing_progression"
    MISSING_GENRE = "missing_genre"
    NO_FINALISTS = "no_finalists"
    UPSERT_FAILED = "upsert_failed"


@dataclass(frozen=True)
class SkipEntry:
    """A single skipped-pattern record for the HarvestReport."""
    candidate_id: str
    pattern_type: str
    reason: SkipReason


@dataclass(frozen=True)
class HarvestReport:
    """Return value of the harvest helper; mirrored to frontend as SSE payload.

    Field names chosen to reflect write-action semantics, not library-size delta:
    `upserted_count` counts MERGE operations (new + idempotent rewrite alike).
    Consumers must treat `upserted_pattern_ids` as an unordered set.
    """
    session_id: str
    upserted_count: int
    skipped_count: int
    skipped_reasons: list[SkipEntry] = field(default_factory=list)
    upserted_pattern_ids: list[str] = field(default_factory=list)
```

- [ ] **Step 1.4: Run the import to verify no syntax errors**

Run: `cd backend && uv run python -c "from explorator.services.pattern_library.harvest_service import HarvestReport, SkipReason, SkipEntry; print('ok')"`
Expected: `ok`

- [ ] **Step 1.5: Commit (WIP — squashed into Commit A at end)**

```bash
git add backend/src/explorator/services/
git commit -m "wip(m5d-2): scaffold pattern_library service package"
```

---

## Task 2: TDD — `harvest_session_finalists_from_state` helper

**Files:**
- Modify: `backend/src/explorator/services/pattern_library/harvest_service.py`
- Create: `backend/tests/services/__init__.py` (if missing)
- Create: `backend/tests/services/pattern_library/__init__.py`
- Create: `backend/tests/services/pattern_library/test_harvest_service.py`

- [ ] **Step 2.1: Write the failing test file**

Create `backend/tests/services/pattern_library/test_harvest_service.py`:

```python
"""Unit tests for harvest_session_finalists_from_state.

Uses the same state-shape fixture as test_m5d1_harvest.py but at the helper level,
so the helper is exercised without any LangGraph or SSE plumbing.
"""
from unittest.mock import AsyncMock

import pytest

from explorator.services.pattern_library.harvest_service import (
    HarvestReport,
    SkipReason,
    harvest_session_finalists_from_state,
)


def _state_with_two_finalists() -> dict:
    """Same shape as backend/tests/integration/test_m5d1_harvest.py builder."""
    return {
        "session_id": "sess_harvest_helper",
        "genre": "dream_pop",
        "final_selection": {
            "selected_candidate_ids": ["arr_01", "arr_02"],
            "selection_roles": {"arr_01": "safest", "arr_02": "best_loop"},
        },
        "arrangement_candidates": [
            {"id": "arr_01", "progression_candidate_id": "prog_01",
             "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
             "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01"},
            {"id": "arr_02", "progression_candidate_id": "prog_02",
             "voicing_plan_id": "vp_02", "bass_line_id": "bl_02",
             "groove_pattern_id": "gp_02", "melodic_complement_id": "mc_02"},
        ],
        "progression_candidates": [
            {"id": "prog_01", "key_center": "A", "mode": "major",
             "chord_symbols": ["Amaj7", "F#m7", "Dmaj7", "E7"], "phrase_length_bars": 4,
             "metadata": {"roman_numerals": ["Imaj7", "vi7", "IVmaj7", "V7"]}},
            {"id": "prog_02", "key_center": "A", "mode": "major",
             "chord_symbols": ["Amaj7", "C#m7", "F#m7", "Dmaj7"], "phrase_length_bars": 4,
             "metadata": {"roman_numerals": ["Imaj7", "iii7", "vi7", "IVmaj7"]}},
        ],
        "voicing_plans": [
            {"id": "vp_01", "strategy": {"register_profile": "mid_high", "density": "medium", "voice_count": 4}},
            {"id": "vp_02", "strategy": {"register_profile": "mid_high", "density": "medium", "voice_count": 4}},
        ],
        "bass_lines": [
            {"id": "bl_01", "mode": "root", "rhythmic_density": 0.4},
            {"id": "bl_02", "mode": "walking", "rhythmic_density": 0.6},
        ],
        "groove_patterns": [
            {"id": "gp_01", "swing_level": 0.3, "syncopation_level": 0.2, "density": 0.5, "template_name": "dream_pop_basic"},
            {"id": "gp_02", "swing_level": 0.5, "syncopation_level": 0.4, "density": 0.7, "template_name": "dream_pop_dense"},
        ],
        "melodic_complements": [
            {"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 12, "rhythmic_density": 0.4}},
            {"id": "mc_02", "strategy": {"contour_type": "descending", "range_semitones": 19, "rhythmic_density": 0.5}},
        ],
        "scorecards": [
            {"candidate_id": "arr_01", "weighted_total": 0.82,
             "scores": {"loopability": 0.85, "cadence_quality": 0.8},
             "pareto_tags": ["pareto_front"]},
            {"candidate_id": "arr_02", "weighted_total": 0.75,
             "scores": {"loopability": 0.7, "cadence_quality": 0.72},
             "pareto_tags": []},
        ],
    }


@pytest.mark.asyncio
async def test_happy_path_upserts_ten_patterns() -> None:
    """2 finalists × 5 facets = 10 upserts; HarvestReport reflects that."""
    repo = AsyncMock()
    repo.upsert = AsyncMock()

    report = await harvest_session_finalists_from_state(
        _state_with_two_finalists(), pattern_library_repo=repo
    )

    assert isinstance(report, HarvestReport)
    assert report.session_id == "sess_harvest_helper"
    assert report.upserted_count == 10
    assert len(report.upserted_pattern_ids) == 10
    assert report.skipped_count == 0
    assert report.skipped_reasons == []
    assert repo.upsert.await_count == 10


@pytest.mark.asyncio
async def test_no_finalists_returns_empty_report() -> None:
    """Empty selected_candidate_ids short-circuits; no upserts attempted."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    state["final_selection"]["selected_candidate_ids"] = []

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    assert report.upserted_count == 0
    assert report.upserted_pattern_ids == []
    assert repo.upsert.await_count == 0


@pytest.mark.asyncio
async def test_missing_genre_skips_harvest() -> None:
    """No genre → skip harvest (polluting the library with 'unknown' genre is worse than skipping)."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    del state["genre"]

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    assert report.upserted_count == 0
    assert report.skipped_count >= 1
    assert all(e.reason == SkipReason.MISSING_GENRE for e in report.skipped_reasons)
    assert repo.upsert.await_count == 0


@pytest.mark.asyncio
async def test_missing_arrangement_records_skip_reason() -> None:
    """A selected_id with no matching arrangement is recorded, not silently dropped."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    state["arrangement_candidates"] = [state["arrangement_candidates"][0]]
    # arr_02 selected but not present in arrangement_candidates

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    # arr_01 still produces 5 upserts
    assert report.upserted_count == 5
    # arr_02 produces a single MISSING_ARRANGEMENT skip (not 5, since we can't
    # know which pattern_types would have applied without the arrangement)
    arr02_skips = [e for e in report.skipped_reasons if e.candidate_id == "arr_02"]
    assert len(arr02_skips) == 1
    assert arr02_skips[0].reason == SkipReason.MISSING_ARRANGEMENT


@pytest.mark.asyncio
async def test_idempotence_via_repo_upsert() -> None:
    """Running twice on the same state produces the same upserted_pattern_ids set
    (MERGE at the repo layer guarantees this; helper must pass entry IDs through)."""
    repo = AsyncMock()
    repo.upsert = AsyncMock()
    state = _state_with_two_finalists()

    report_a = await harvest_session_finalists_from_state(state, pattern_library_repo=repo)
    report_b = await harvest_session_finalists_from_state(state, pattern_library_repo=repo)

    assert set(report_a.upserted_pattern_ids) == set(report_b.upserted_pattern_ids)
```

- [ ] **Step 2.2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/services/pattern_library/test_harvest_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'harvest_session_finalists_from_state'`

- [ ] **Step 2.3: Implement the helper**

Append to `backend/src/explorator/services/pattern_library/harvest_service.py`:

```python
import logging
from typing import Any

from neo4j.exceptions import Neo4jError

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


async def harvest_session_finalists_from_state(
    state: dict[str, Any],
    *,
    pattern_library_repo: PatternLibraryRepo,
) -> HarvestReport:
    """Harvest patterns from a LangGraph state dict.

    Transport-free: does not emit SSE, does not touch LangGraph state mechanics.
    Reads finalist facets directly from the in-memory state dict (the shape used
    by the `harvest_patterns` node). The public `harvest_session_finalists`
    entry point (added in Commit B) reads the same facets from repos via
    session_id and delegates to this function.
    """
    session_id = state.get("session_id", "")
    final_selection = state.get("final_selection") or {}
    selected_ids: list[str] = final_selection.get("selected_candidate_ids") or []
    genre = state.get("genre")

    if not selected_ids:
        return HarvestReport(
            session_id=session_id, upserted_count=0, skipped_count=0,
        )

    if not genre:
        logger.warning(
            "harvest_session_finalists: no genre in state for session %s; skipping",
            session_id or "?",
        )
        skipped = [
            SkipEntry(candidate_id=cid, pattern_type="*", reason=SkipReason.MISSING_GENRE)
            for cid in selected_ids
        ]
        return HarvestReport(
            session_id=session_id, upserted_count=0,
            skipped_count=len(skipped), skipped_reasons=skipped,
        )

    roles: dict[str, str] = final_selection.get("selection_roles") or {}
    arrangements = _index_by_id(state.get("arrangement_candidates") or [])
    progressions = _index_by_id(state.get("progression_candidates") or [])
    voicing_plans = _index_by_id(state.get("voicing_plans") or [])
    bass_lines = _index_by_id(state.get("bass_lines") or [])
    grooves = _index_by_id(state.get("groove_patterns") or [])
    melodies = _index_by_id(state.get("melodic_complements") or [])
    scorecards_by_cand = {
        s["candidate_id"]: s
        for s in (state.get("scorecards") or [])
        if s.get("candidate_id")
    }

    upserted_ids: list[str] = []
    skipped: list[SkipEntry] = []

    for arr_id in selected_ids:
        arrangement = arrangements.get(arr_id)
        if arrangement is None:
            skipped.append(SkipEntry(
                candidate_id=arr_id, pattern_type="*",
                reason=SkipReason.MISSING_ARRANGEMENT,
            ))
            continue
        progression = progressions.get(arrangement.get("progression_candidate_id"))
        if progression is None:
            skipped.append(SkipEntry(
                candidate_id=arr_id, pattern_type="*",
                reason=SkipReason.MISSING_PROGRESSION,
            ))
            continue
        scorecard = scorecards_by_cand.get(arr_id) or {
            "weighted_total": 0.0, "scores": {}, "pareto_tags": [],
        }
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
        # Per-entry try/except: one Neo4j failure doesn't block siblings. The catch
        # is narrowed to Neo4jError so programming errors (KeyError, AttributeError)
        # surface loudly instead of hiding.
        for entry in entries:
            try:
                await pattern_library_repo.upsert(entry)
                upserted_ids.append(entry.id)
            except Neo4jError as exc:
                logger.error(
                    "harvest_session_finalists: failed to upsert entry %s (%s/%s): %s",
                    entry.id, entry.pattern_type, entry.source_candidate_id, exc,
                )
                skipped.append(SkipEntry(
                    candidate_id=entry.source_candidate_id,
                    pattern_type=entry.pattern_type,
                    reason=SkipReason.UPSERT_FAILED,
                ))

    return HarvestReport(
        session_id=session_id,
        upserted_count=len(upserted_ids),
        skipped_count=len(skipped),
        skipped_reasons=skipped,
        upserted_pattern_ids=upserted_ids,
    )
```

- [ ] **Step 2.4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/services/pattern_library/test_harvest_service.py -v`
Expected: 5 PASS

- [ ] **Step 2.5: Commit (WIP)**

```bash
git add backend/src/explorator/services/pattern_library/harvest_service.py \
        backend/tests/services/
git commit -m "wip(m5d-2): harvest_session_finalists_from_state helper + unit tests"
```

---

## Task 3: Refactor `harvest_patterns` node to call the helper

**Files:**
- Modify: `backend/src/explorator/engine/nodes/harvest_patterns.py`

- [ ] **Step 3.1: Replace the node body with a thin wrapper**

Replace the entire file contents of `backend/src/explorator/engine/nodes/harvest_patterns.py` with:

```python
"""LangGraph node: auto-harvest patterns from finalist arrangements.

Thin wrapper around services.pattern_library.harvest_session_finalists_from_state.
Responsibilities kept at this layer:
  1. Emit the three SSE progress events (node_started, pattern_harvest, node_completed)
     with the exact payload shapes M5d-1 established.
  2. Translate HarvestReport → the legacy {"harvested_pattern_ids": [...]} return
     shape expected by existing graph tests.

All orchestration (state indexing, per-finalist loop, repo upsert, error handling)
lives in the service module.
"""
import logging
from typing import Any

from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.services.pattern_library.harvest_service import (
    harvest_session_finalists_from_state,
)

logger = logging.getLogger(__name__)


async def harvest_patterns(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    callback = state.get("on_progress")
    if callback is not None:
        await callback("node_started", {"node": "harvest_patterns"})

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo,
    )

    # Happy-path domain event: only emitted when something was actually harvested.
    # Preserves M5d-1 semantics (legacy callers observe count + genre keys).
    if callback is not None and report.upserted_count > 0:
        genre = state.get("genre")
        await callback("pattern_harvest", {"count": report.upserted_count, "genre": genre})

    if callback is not None:
        await callback(
            "node_completed",
            {"node": "harvest_patterns", "count": report.upserted_count},
        )

    return {"harvested_pattern_ids": list(report.upserted_pattern_ids)}
```

- [ ] **Step 3.2: Run the existing M5d-1 regression test**

Run: `cd backend && uv run pytest tests/integration/test_m5d1_harvest.py -v`
Expected: all 4 tests PASS unchanged. If Neo4j is unreachable, they skip — that's OK; re-run after starting the container with `docker compose up -d neo4j`.

- [ ] **Step 3.3: Run the new helper test**

Run: `cd backend && uv run pytest tests/services/pattern_library/test_harvest_service.py -v`
Expected: 5 PASS.

- [ ] **Step 3.4: Run the full backend test suite to catch any collateral breakage**

Run: `cd backend && uv run pytest -q`
Expected: green (or same pre-existing skips as `main`).

- [ ] **Step 3.5: Squash WIPs into Commit A and commit**

```bash
git add backend/src/explorator/engine/nodes/harvest_patterns.py \
        backend/src/explorator/services/ backend/tests/services/
git reset --soft $(git merge-base main HEAD)
git commit -m "$(cat <<'EOF'
refactor(m5d-2): extract harvest orchestration into pattern_library service

Pure extraction — no behavior change at the node's external contract:
- harvest_patterns node still returns {"harvested_pattern_ids": [...]} and
  emits the same three progress events with identical payloads.
- New module services/pattern_library/harvest_service.py holds the transport-free
  orchestration (state indexing, per-finalist loop, upserts, skip-reason tracking).
- Typed HarvestReport + SkipReason enum prepare the payload shape for Commit B's
  SSE wire contract; node wrapper translates to legacy dict shape.

The helper is test-covered with AsyncMock repos at tests/services/pattern_library/
test_harvest_service.py. Existing test_m5d1_harvest.py integration tests pass
unchanged, verifying the regression guard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Commit B — Library API + frontend

Tasks 4–21 land in a single logical commit, but work proceeds task-by-task with WIP commits; they are squashed at the end of Task 21.

## Task 4: Add `deleted_at` to `PatternLibraryEntry` + upsert clears it

**Files:**
- Modify: `backend/src/explorator/models/memory.py:33-45`
- Modify: `backend/src/explorator/graph/pattern_library_repo.py:20-56`

- [ ] **Step 4.1: Add the field to the Pydantic model**

Edit `backend/src/explorator/models/memory.py`, replacing the existing `PatternLibraryEntry` class body (lines 33-45) with:

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
    # Soft-delete tombstone. Set by soft_delete; cleared unconditionally by upsert ON MATCH.
    # Rows with deleted_at != None are invisible to list_page / get_by_id / iter_all.
    deleted_at: datetime | None = None
    # TODO(vector): when embeddings ship, populate from an embedder service and
    # swap GraphRetrieval for a vector-backed retrieval in fetch_warm_starts.
    embedding: list[float] | None = None
```

Add the import at the top of `memory.py` if missing:

```python
from datetime import datetime
```

- [ ] **Step 4.2: Update `upsert` to clear `deleted_at` on MATCH**

In `backend/src/explorator/graph/pattern_library_repo.py`, replace the Cypher string in the `upsert` method (around lines 41-49) with:

```python
        query = """
        MERGE (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt})
        ON CREATE SET p = $props,
                      p.id = $id,
                      p.source_candidate_id = $scid,
                      p.pattern_type = $pt,
                      p.created_at = $created_at
        ON MATCH  SET p += $props,
                      p.deleted_at = NULL
        """
```

The `p.deleted_at = NULL` runs unconditionally (no WHERE predicate) — per spec §3.1 invariant #2.

- [ ] **Step 4.3: Run existing repo + harvest tests to confirm no breakage**

Run: `cd backend && uv run pytest tests/integration/test_m5d1_harvest.py tests/services/pattern_library/ -v`
Expected: all PASS.

- [ ] **Step 4.4: Commit (WIP)**

```bash
git add backend/src/explorator/models/memory.py \
        backend/src/explorator/graph/pattern_library_repo.py
git commit -m "wip(m5d-2): add deleted_at column + upsert clears it unconditionally"
```

---

## Task 5: Neo4j index migration script

**Files:**
- Create: `backend/scripts/migrations/m5d2_pattern_library_indexes.py`

- [ ] **Step 5.1: Create the migration**

```python
"""M5d-2 migration: add sort index for keyset pagination on PatternLibraryEntry.

Neo4j is schemaless, so no column creation is needed for the new `deleted_at`
property — new writes will carry it, existing rows return NULL (treated as
"not deleted" by list_page's WHERE deleted_at IS NULL filter).

This script is idempotent (IF NOT EXISTS) and safe on clean databases.

Usage:
    # Preview mode — shows what would be created.
    uv run python scripts/migrations/m5d2_pattern_library_indexes.py

    # Apply mode — actually creates the index.
    uv run python scripts/migrations/m5d2_pattern_library_indexes.py --yes
"""
import argparse
import asyncio
import os
import sys

from explorator.graph.connection import get_driver


INDEX_CYPHER = """
CREATE INDEX pattern_library_sort_idx IF NOT EXISTS
  FOR (p:PatternLibraryEntry) ON (p.weighted_total, p.id)
"""


async def _index_exists(driver) -> bool:
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "SHOW INDEXES YIELD name WHERE name = 'pattern_library_sort_idx' RETURN name"
        )
        record = await result.single()
        return record is not None


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d2-indexes] Target Neo4j: {uri}")

    driver = await get_driver()
    try:
        already = await _index_exists(driver)
        if already:
            print("[m5d2-indexes] Index pattern_library_sort_idx already exists. Nothing to do.")
            return 0

        if not apply:
            print(
                "[m5d2-indexes] Would create composite index on "
                "(:PatternLibraryEntry {weighted_total, id})."
            )
            print("[m5d2-indexes] Re-run with --yes to apply.")
            return 0

        async with driver.session() as neo_session:
            await neo_session.run(INDEX_CYPHER)
        print("[m5d2-indexes] Created pattern_library_sort_idx.")
        return 0
    finally:
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
```

- [ ] **Step 5.2: Run it in preview mode**

Run: `cd backend && uv run python scripts/migrations/m5d2_pattern_library_indexes.py`
Expected: `Would create composite index ...`

- [ ] **Step 5.3: Apply it**

Run: `cd backend && uv run python scripts/migrations/m5d2_pattern_library_indexes.py --yes`
Expected: `Created pattern_library_sort_idx.`

- [ ] **Step 5.4: Verify**

Run: `docker exec explorator-neo4j-1 cypher-shell -u neo4j -p explorator_dev "SHOW INDEXES YIELD name WHERE name = 'pattern_library_sort_idx' RETURN name"`
Expected: one row with `pattern_library_sort_idx`.

- [ ] **Step 5.5: Commit (WIP)**

```bash
git add backend/scripts/migrations/m5d2_pattern_library_indexes.py
git commit -m "wip(m5d-2): migration — add pattern_library keyset-sort index"
```

---

## Task 6: TDD — cursor module

**Files:**
- Create: `backend/src/explorator/services/pattern_library/cursor.py`
- Create: `backend/tests/services/pattern_library/test_cursor.py`

- [ ] **Step 6.1: Write the failing test**

```python
"""Unit tests for pattern_library.cursor."""
import pytest

from explorator.services.pattern_library.cursor import (
    Cursor,
    InvalidCursor,
    parse_cursor,
)


def test_parse_none_none_returns_none() -> None:
    assert parse_cursor(None, None) is None


def test_parse_both_set_returns_cursor() -> None:
    result = parse_cursor(0.87, "01J_abc")
    assert result == Cursor(after_score=0.87, after_id="01J_abc")


def test_parse_only_score_raises() -> None:
    with pytest.raises(InvalidCursor):
        parse_cursor(0.5, None)


def test_parse_only_id_raises() -> None:
    with pytest.raises(InvalidCursor):
        parse_cursor(None, "01J_abc")
```

- [ ] **Step 6.2: Run to confirm it fails**

Run: `cd backend && uv run pytest tests/services/pattern_library/test_cursor.py -v`
Expected: FAIL — ImportError.

- [ ] **Step 6.3: Implement `cursor.py`**

```python
"""Plaintext keyset cursor for PatternLibraryRepo.list_page.

Chosen over opaque base64 encoding: library browser is internal tooling, so
DevTools-legibility beats API-contract opacity. Router emits `after_score` /
`after_id` as separate query params and response fields.
"""
from dataclasses import dataclass


class InvalidCursor(Exception):
    """Raised when exactly one of (after_score, after_id) is set."""


@dataclass(frozen=True)
class Cursor:
    after_score: float
    after_id: str


def parse_cursor(
    after_score: float | None,
    after_id: str | None,
) -> Cursor | None:
    """None if both are None; Cursor if both are set; raises InvalidCursor otherwise."""
    if after_score is None and after_id is None:
        return None
    if after_score is None or after_id is None:
        raise InvalidCursor(
            "after_score and after_id must be set together (either both or neither)"
        )
    return Cursor(after_score=after_score, after_id=after_id)
```

- [ ] **Step 6.4: Run the test**

Run: `cd backend && uv run pytest tests/services/pattern_library/test_cursor.py -v`
Expected: 4 PASS.

- [ ] **Step 6.5: Commit (WIP)**

```bash
git add backend/src/explorator/services/pattern_library/cursor.py \
        backend/tests/services/pattern_library/test_cursor.py
git commit -m "wip(m5d-2): cursor module (parse_cursor, Cursor, InvalidCursor)"
```

---

## Task 7: TDD — `PatternFilters` + repo `list_page` with keyset pagination

**Files:**
- Create: `backend/src/explorator/services/pattern_library/filters.py`
- Modify: `backend/src/explorator/graph/pattern_library_repo.py`
- Create: `backend/tests/integration/test_pattern_library_repo_pagination.py`

- [ ] **Step 7.1: Create `filters.py`**

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
```

- [ ] **Step 7.2: Write the failing integration test**

Create `backend/tests/integration/test_pattern_library_repo_pagination.py`:

```python
"""Integration tests for PatternLibraryRepo.list_page keyset pagination.

Runs against the real Neo4j test container. Exercises off-by-one, tiebreaker,
filter combinations, and the soft-delete filter.
"""
from datetime import datetime

import pytest
from neo4j import AsyncDriver

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.cursor import Cursor
from explorator.services.pattern_library.filters import PatternFilters


def _entry(
    *, idx: int, score: float, genre: str = "dream_pop", ptype: str = "progression",
    source_suffix: str = "",
) -> PatternLibraryEntry:
    return PatternLibraryEntry(
        id=f"pat_{idx:04d}",
        type="pattern_library_entry",
        status="active",
        created_at=datetime(2026, 4, 19, 12, 0, 0),
        updated_at=datetime(2026, 4, 19, 12, 0, 0),
        pattern_type=ptype,
        genre=genre,
        tags=[],
        source_candidate_id=f"cand_{idx:04d}{source_suffix}",
        abstracted_pattern={},
        success_metrics={"weighted_total": score},
        notes="",
    )


async def _wipe(driver: AsyncDriver) -> None:
    async with driver.session() as neo:
        await neo.run("MATCH (p:PatternLibraryEntry) DETACH DELETE p")


@pytest.mark.asyncio
async def test_first_page_returns_limit_plus_cursor(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    # Insert 8 rows, scores 0.80 .. 0.15 descending
    for i in range(8):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    items, next_cursor = await repo.list_page(limit=5)

    assert len(items) == 5
    assert [e["success_metrics"]["weighted_total"] for e in items] == pytest.approx(
        [0.80, 0.70, 0.60, 0.50, 0.40]
    )
    assert next_cursor is not None


@pytest.mark.asyncio
async def test_cursor_round_trip_returns_next_page(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(8):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    page1, cursor1 = await repo.list_page(limit=5)
    assert cursor1 is not None

    page2, cursor2 = await repo.list_page(cursor=cursor1, limit=5)

    assert len(page2) == 3  # 8 total - 5 shown = 3 remaining
    page1_ids = {e["id"] for e in page1}
    page2_ids = {e["id"] for e in page2}
    assert page1_ids.isdisjoint(page2_ids)
    assert cursor2 is None  # terminal


@pytest.mark.asyncio
async def test_terminal_page_exact_limit_no_next_cursor(neo4j_driver: AsyncDriver) -> None:
    """Off-by-one guard: exactly `limit` rows remaining → next_cursor=None."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(5):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    items, next_cursor = await repo.list_page(limit=5)

    assert len(items) == 5
    assert next_cursor is None


@pytest.mark.asyncio
async def test_tiebreaker_identical_weighted_total(neo4j_driver: AsyncDriver) -> None:
    """3 rows with identical weighted_total, limit=2 → no dupes, no skips across pages."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(3):
        await repo.upsert(_entry(idx=i, score=0.50, source_suffix=f"_tie{i}"))

    page1, cursor = await repo.list_page(limit=2)
    assert cursor is not None
    assert len(page1) == 2

    page2, cursor2 = await repo.list_page(cursor=cursor, limit=2)
    assert len(page2) == 1
    assert cursor2 is None

    all_ids = {e["id"] for e in page1} | {e["id"] for e in page2}
    assert len(all_ids) == 3  # no dupes, no skips


@pytest.mark.asyncio
async def test_filter_by_genre_only(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, genre="dream_pop"))
    await repo.upsert(_entry(idx=2, score=0.7, genre="jazz"))

    items, _ = await repo.list_page(filters=PatternFilters(genre="dream_pop"))

    assert len(items) == 1
    assert items[0]["genre"] == "dream_pop"


@pytest.mark.asyncio
async def test_filter_by_pattern_type_only(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, ptype="progression"))
    await repo.upsert(_entry(idx=2, score=0.7, ptype="voicing"))

    items, _ = await repo.list_page(filters=PatternFilters(pattern_type="voicing"))

    assert len(items) == 1
    assert items[0]["pattern_type"] == "voicing"


@pytest.mark.asyncio
async def test_soft_deleted_rows_hidden(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))
    await repo.upsert(_entry(idx=2, score=0.7))
    await repo.soft_delete("pat_0001")

    items, _ = await repo.list_page()

    assert len(items) == 1
    assert items[0]["id"] == "pat_0002"
```

- [ ] **Step 7.3: Run the test to confirm it fails (no list_page yet)**

Run: `cd backend && uv run pytest tests/integration/test_pattern_library_repo_pagination.py -v`
Expected: FAIL — `AttributeError: 'PatternLibraryRepo' object has no attribute 'list_page'`.

- [ ] **Step 7.4: Add `list_page`, `iter_all`, and `soft_delete` to the repo**

In `backend/src/explorator/graph/pattern_library_repo.py`, add the imports at the top:

```python
from collections.abc import AsyncIterator
from datetime import datetime

from explorator.services.pattern_library.cursor import Cursor
from explorator.services.pattern_library.filters import PatternFilters
from explorator.utils import utc_now
```

Then append to the `PatternLibraryRepo` class (after `query_for_warm_starts`):

```python
    async def list_page(
        self,
        *,
        filters: PatternFilters | None = None,
        cursor: Cursor | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], Cursor | None]:
        """Bounded keyset-paginated list of non-deleted patterns.

        Order: weighted_total DESC, id ASC (compound tiebreaker). Emits a
        Cursor over the last returned row's (weighted_total, id) pair; None
        when the page is terminal. Caller-supplied `limit` must be bounded —
        no unbounded sentinel is accepted (use `iter_all` for unbounded reads).
        """
        filters = filters or PatternFilters()
        params: dict[str, Any] = {
            "genre": filters.genre,
            "ptype": filters.pattern_type,
            "after_score": cursor.after_score if cursor else None,
            "after_id": cursor.after_id if cursor else None,
            "limit": limit,
        }
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
          AND ($after_score IS NULL
               OR p.weighted_total < $after_score
               OR (p.weighted_total = $after_score AND p.id > $after_id))
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        LIMIT $limit + 1
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            records = [r async for r in result]

        entries = [_neo4j_deserialize(dict(rec["p"])) for rec in records]
        next_cursor: Cursor | None = None
        if len(entries) > limit:
            overflow = entries[limit - 1]  # the last in-window row becomes the cursor
            next_cursor = Cursor(
                after_score=float(overflow["success_metrics"].get("weighted_total") or 0.0),
                after_id=str(overflow["id"]),
            )
            entries = entries[:limit]
        return entries, next_cursor

    async def iter_all(
        self,
        *,
        filters: PatternFilters | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Unbounded internal generator over non-deleted patterns.

        Not exposed via the HTTP API. Used by internal consumers that need to
        stream the full library (e.g. query_for_warm_starts). Order is the same
        as list_page (weighted_total DESC, id ASC) for consumer consistency.
        """
        filters = filters or PatternFilters()
        params = {"genre": filters.genre, "ptype": filters.pattern_type}
        query = """
        MATCH (p:PatternLibraryEntry)
        WHERE p.deleted_at IS NULL
          AND ($genre IS NULL OR p.genre = $genre)
          AND ($ptype IS NULL OR p.pattern_type = $ptype)
        RETURN p
        ORDER BY p.weighted_total DESC, p.id ASC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, **params)
            async for record in result:
                yield _neo4j_deserialize(dict(record["p"]))

    async def soft_delete(self, entry_id: str) -> bool:
        """Mark a pattern as deleted by setting deleted_at. Returns False if the
        row is missing or already deleted — callers translate to HTTP 404.
        """
        query = """
        MATCH (p:PatternLibraryEntry {id: $id})
        WHERE p.deleted_at IS NULL
        SET p.deleted_at = $now
        RETURN p.id AS id
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(
                query, id=entry_id, now=utc_now().isoformat()
            )
            record = await result.single()
            return record is not None
```

Also update `get_by_id` to filter soft-deleted rows:

```python
    async def get_by_id(self, entry_id: str) -> dict[str, Any] | None:
        query = """
        MATCH (p:PatternLibraryEntry {id: $id})
        WHERE p.deleted_at IS NULL
        RETURN p
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, id=entry_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["p"]))
```

- [ ] **Step 7.5: Run the pagination test**

Run: `cd backend && uv run pytest tests/integration/test_pattern_library_repo_pagination.py -v`
Expected: 7 PASS.

- [ ] **Step 7.6: Commit (WIP)**

```bash
git add backend/src/explorator/services/pattern_library/filters.py \
        backend/src/explorator/graph/pattern_library_repo.py \
        backend/tests/integration/test_pattern_library_repo_pagination.py
git commit -m "wip(m5d-2): add PatternFilters + list_page/iter_all/soft_delete repo methods"
```

---

## Task 8: Migrate `query_for_warm_starts` to `iter_all`; remove `list_all`

**Files:**
- Modify: `backend/src/explorator/graph/pattern_library_repo.py` (remove `list_all`, update `query_for_warm_starts`)

- [ ] **Step 8.1: Replace `query_for_warm_starts` body**

In `backend/src/explorator/graph/pattern_library_repo.py`, replace the existing `query_for_warm_starts` method with:

```python
    async def query_for_warm_starts(
        self,
        *,
        genre: str,
        top_k_per_type: int = 5,
        tag_filters: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return top-K patterns per pattern_type for a genre, ordered by weighted_total DESC.

        Streams via iter_all to avoid pulling the full genre slice into memory at once.
        Tag filtering is client-side (acceptable at current cardinality; see M5d-3 note
        on pushing into Cypher when cardinality warrants).
        """
        filters = PatternFilters(genre=genre)
        grouped: dict[str, list[dict[str, Any]]] = {}
        async for entry in self.iter_all(filters=filters):
            if tag_filters and not all(t in (entry.get("tags") or []) for t in tag_filters):
                continue
            bucket = grouped.setdefault(entry["pattern_type"], [])
            if len(bucket) < top_k_per_type:
                bucket.append(entry)
        return grouped
```

- [ ] **Step 8.2: Delete `list_all` entirely**

Remove the `list_all` method from the file (roughly lines 67-101 in the original file).

- [ ] **Step 8.3: Grep for any remaining callers of `list_all`**

Run: `cd backend && grep -rn "list_all" src/ tests/`
Expected: no results for `PatternLibraryRepo.list_all` usage. If anything is found, migrate it to `list_page` (bounded API) or `iter_all` (unbounded internal).

- [ ] **Step 8.4: Run the full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: green. Warm-start retrieval tests (if any) should still pass because `query_for_warm_starts` preserves its external contract.

- [ ] **Step 8.5: Commit (WIP)**

```bash
git add backend/src/explorator/graph/pattern_library_repo.py
git commit -m "wip(m5d-2): migrate query_for_warm_starts to iter_all; remove list_all"
```

---

## Task 9: `PatternItem` Pydantic schema + public `harvest_session_finalists` entry point

**Files:**
- Create: `backend/src/explorator/api/schemas/patterns.py`
- Create: `backend/src/explorator/api/schemas/__init__.py` (if missing)
- Modify: `backend/src/explorator/services/pattern_library/harvest_service.py`

- [ ] **Step 9.1: Create the schemas module if absent**

Run: `ls backend/src/explorator/api/schemas/ 2>&1`
If missing: `mkdir -p backend/src/explorator/api/schemas && touch backend/src/explorator/api/schemas/__init__.py`

- [ ] **Step 9.2: Write `PatternItem` response schema + paginated envelope**

Create `backend/src/explorator/api/schemas/patterns.py`:

```python
"""API schemas for the pattern library endpoints."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class CursorResponse(BaseModel):
    after_score: float
    after_id: str


class PatternListResponse(BaseModel):
    items: list[PatternItem]
    next_cursor: CursorResponse | None = None


class SkipEntryResponse(BaseModel):
    candidate_id: str
    pattern_type: str
    reason: str  # serialized SkipReason value


class HarvestReportResponse(BaseModel):
    session_id: str
    upserted_count: int
    skipped_count: int
    skipped_reasons: list[SkipEntryResponse] = Field(default_factory=list)
    upserted_pattern_ids: list[str] = Field(default_factory=list)
```

- [ ] **Step 9.3: Add the `HarvestRepos` dataclass and public helper**

Append to `backend/src/explorator/services/pattern_library/harvest_service.py`:

```python
from dataclasses import dataclass as _dataclass  # re-import alias not needed if already in file

# NOTE: HarvestRepos is a composition bundle constructed in deps.py (composition
# root) and passed to harvest_session_finalists. The helper reads finalists from
# these repos via session_id — used by the POST /v1/sessions/{id}/finalists/harvest
# endpoint. The LangGraph node uses harvest_session_finalists_from_state instead
# (reads from in-memory state to avoid a DB round-trip at realization time).


@dataclass(frozen=True)
class HarvestRepos:
    """Bundle of repos needed by the session-id-driven harvest path.

    Progression candidates live only on arrangements via progression_candidate_id —
    ProgressionCandidateRepo is not a separate persistent repo; progression data
    is reconstructed from state or from the ArrangementCandidateRepo's metadata.
    """
    pattern_library: PatternLibraryRepo
    arrangement_candidate: Any   # ArrangementCandidateRepo (imported at call site)
    bass_line: Any               # BassLineRepo
    voicing_plan: Any            # VoicingPlanRepo
    groove_pattern: Any          # GroovePatternRepo
    melodic_complement: Any      # MelodicComplementRepo


async def harvest_session_finalists(
    session_id: str,
    *,
    repos: HarvestRepos,
) -> HarvestReport:
    """Read finalists from repos, harvest patterns, upsert. Idempotent.

    Use from API endpoints (where finalists are already persisted); the
    LangGraph node uses harvest_session_finalists_from_state.
    """
    # Build a state-shaped dict from repo reads, then delegate.
    state = await _reconstruct_state_from_repos(session_id, repos=repos)
    return await harvest_session_finalists_from_state(
        state, pattern_library_repo=repos.pattern_library,
    )


async def _reconstruct_state_from_repos(
    session_id: str,
    *,
    repos: HarvestRepos,
) -> dict[str, Any]:
    """Pull finalists + facets from repos into a state-shaped dict.

    This function is the boundary between the repo-indexed world (used by
    the API endpoint) and the state-indexed world (used by the LangGraph
    node and the core harvest loop). It queries the arrangement repo for
    session-scoped arrangements whose metadata carries a finalist role.
    """
    # Arrangements with metadata.role stamped by persist_realization are finalists.
    arrangements = await repos.arrangement_candidate.list_finalists_for_session(session_id)

    selected_ids = [a["id"] for a in arrangements]
    roles = {a["id"]: a.get("metadata", {}).get("role", "unknown") for a in arrangements}

    # Facet fan-out. Each arrangement has *_id pointers; fetch each facet once.
    voicing_ids = {a.get("voicing_plan_id") for a in arrangements if a.get("voicing_plan_id")}
    bass_ids = {a.get("bass_line_id") for a in arrangements if a.get("bass_line_id")}
    groove_ids = {a.get("groove_pattern_id") for a in arrangements if a.get("groove_pattern_id")}
    melody_ids = {a.get("melodic_complement_id") for a in arrangements if a.get("melodic_complement_id")}
    prog_ids = {a.get("progression_candidate_id") for a in arrangements if a.get("progression_candidate_id")}

    voicings = [await repos.voicing_plan.get_by_id(i) for i in voicing_ids]
    basses = [await repos.bass_line.get_by_id(i) for i in bass_ids]
    grooves = [await repos.groove_pattern.get_by_id(i) for i in groove_ids]
    melodies = [await repos.melodic_complement.get_by_id(i) for i in melody_ids]
    progressions = [
        await repos.arrangement_candidate.get_progression_candidate(i) for i in prog_ids
    ]

    # Scorecards: pulled via arrangement_candidate repo if it exposes them;
    # otherwise the weighted_total on arrangement metadata is the single source.
    scorecards = [
        {
            "candidate_id": a["id"],
            "weighted_total": a.get("weighted_total", 0.0),
            "scores": a.get("metadata", {}).get("scores", {}),
            "pareto_tags": a.get("metadata", {}).get("pareto_tags", []),
        }
        for a in arrangements
    ]

    # Genre: arrangements inherit session genre via metadata or top-level field.
    genre = None
    if arrangements:
        first = arrangements[0]
        genre = first.get("genre") or first.get("metadata", {}).get("genre")

    return {
        "session_id": session_id,
        "genre": genre,
        "final_selection": {
            "selected_candidate_ids": selected_ids,
            "selection_roles": roles,
        },
        "arrangement_candidates": arrangements,
        "progression_candidates": [p for p in progressions if p],
        "voicing_plans": [v for v in voicings if v],
        "bass_lines": [b for b in basses if b],
        "groove_patterns": [g for g in grooves if g],
        "melodic_complements": [m for m in melodies if m],
        "scorecards": scorecards,
    }
```

- [ ] **Step 9.4: Confirm `ArrangementCandidateRepo.list_finalists_for_session` exists**

Run: `cd backend && grep -rn "list_finalists_for_session\|list_by_session" src/explorator/graph/arrangement_candidate_repo.py`

If not present, add a method to the arrangement repo returning arrangements with `metadata.role` set for a given session. This is a small helper — add it in the same file:

```python
    async def list_finalists_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Return arrangements for a session that carry a finalist role in metadata."""
        query = """
        MATCH (a:ArrangementCandidate {session_id: $sid})
        WHERE a.metadata IS NOT NULL
          AND a.metadata CONTAINS '"role"'
        RETURN a
        ORDER BY a.weighted_total DESC
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, sid=session_id)
            records = [r async for r in result]
        return [_neo4j_deserialize(dict(r["a"])) for r in records]

    async def get_progression_candidate(self, pc_id: str) -> dict[str, Any] | None:
        """Fetch a progression candidate by id (used during harvest reconstruction)."""
        query = """
        MATCH (p:ProgressionCandidate {id: $id})
        RETURN p
        """
        async with self._driver.session() as neo_session:
            result = await neo_session.run(query, id=pc_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["p"]))
```

(Exact imports/structure may differ if the repo already extends `BaseRepository` — follow existing conventions.)

- [ ] **Step 9.5: Run backend suite**

Run: `cd backend && uv run pytest -q`
Expected: green (no new tests in this task — Task 11 will test the public helper via the router).

- [ ] **Step 9.6: Commit (WIP)**

```bash
git add backend/src/explorator/api/schemas/ \
        backend/src/explorator/services/pattern_library/harvest_service.py \
        backend/src/explorator/graph/arrangement_candidate_repo.py
git commit -m "wip(m5d-2): PatternItem schema + public harvest_session_finalists entry point"
```

---

## Task 10: TDD — `/v1/patterns` router (list, get, delete)

**Files:**
- Create: `backend/src/explorator/api/routes/patterns.py`
- Modify: `backend/src/explorator/api/deps.py`
- Modify: `backend/src/explorator/api/app.py`
- Create: `backend/tests/api/test_patterns_router.py`

- [ ] **Step 10.1: Add the DI wiring in `deps.py`**

Append to `backend/src/explorator/api/deps.py`:

```python
async def get_pattern_library_repo():
    """Get pattern library repository dependency."""
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    driver = await get_driver()
    return PatternLibraryRepo(driver)


async def get_harvest_repos():
    """Compose the HarvestRepos bundle for POST /v1/sessions/{id}/finalists/harvest."""
    from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
    from explorator.graph.bass_line_repo import BassLineRepo
    from explorator.graph.groove_pattern_repo import GroovePatternRepo
    from explorator.graph.melodic_complement_repo import MelodicComplementRepo
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo
    from explorator.services.pattern_library.harvest_service import HarvestRepos

    driver = await get_driver()
    return HarvestRepos(
        pattern_library=PatternLibraryRepo(driver),
        arrangement_candidate=ArrangementCandidateRepo(driver),
        voicing_plan=VoicingPlanRepo(driver),
        bass_line=BassLineRepo(driver),
        groove_pattern=GroovePatternRepo(driver),
        melodic_complement=MelodicComplementRepo(driver),
    )
```

- [ ] **Step 10.2: Write the failing router tests**

Create `backend/tests/api/test_patterns_router.py`:

```python
"""FastAPI TestClient tests for /v1/patterns endpoints.

Uses a real Neo4j test container (via the neo4j_driver fixture). Each test
wipes and seeds PatternLibraryEntry rows, then exercises the router.
"""
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncDriver

from explorator.api.app import create_app
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


def _entry(idx: int, score: float, genre: str = "dream_pop", ptype: str = "progression") -> PatternLibraryEntry:
    from datetime import datetime
    return PatternLibraryEntry(
        id=f"pat_{idx:04d}",
        type="pattern_library_entry",
        status="active",
        created_at=datetime(2026, 4, 19),
        updated_at=datetime(2026, 4, 19),
        pattern_type=ptype,
        genre=genre,
        tags=[],
        source_candidate_id=f"cand_{idx:04d}",
        abstracted_pattern={},
        success_metrics={"weighted_total": score},
        notes="",
    )


async def _wipe(driver: AsyncDriver) -> None:
    async with driver.session() as neo:
        await neo.run("MATCH (p:PatternLibraryEntry) DETACH DELETE p")


@pytest.mark.asyncio
async def test_list_patterns_returns_items_and_cursor(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(3):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?limit=2")

    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    assert "after_score" in body["next_cursor"]
    assert "after_id" in body["next_cursor"]


@pytest.mark.asyncio
async def test_list_patterns_filter_by_genre(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, genre="dream_pop"))
    await repo.upsert(_entry(idx=2, score=0.7, genre="jazz"))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?genre=jazz")

    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["genre"] == "jazz"


@pytest.mark.asyncio
async def test_list_patterns_invalid_cursor_returns_400(neo4j_driver: AsyncDriver) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?after_score=0.5")  # missing after_id

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_get_pattern_by_id_happy_path(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns/pat_0001")

    assert res.status_code == 200
    assert res.json()["id"] == "pat_0001"


@pytest.mark.asyncio
async def test_get_pattern_by_id_missing_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns/pat_missing")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_then_get_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_del = await client.delete("/v1/patterns/pat_0001")
        assert res_del.status_code == 204

        res_get = await client.get("/v1/patterns/pat_0001")
        assert res_get.status_code == 404


@pytest.mark.asyncio
async def test_delete_twice_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.delete("/v1/patterns/pat_0001")).status_code == 204
        assert (await client.delete("/v1/patterns/pat_0001")).status_code == 404


@pytest.mark.asyncio
async def test_re_upsert_resurrects_soft_deleted(neo4j_driver: AsyncDriver) -> None:
    """Upsert with same natural key clears deleted_at (MERGE ON MATCH SET deleted_at = NULL)."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))
    await repo.soft_delete("pat_0001")
    assert await repo.get_by_id("pat_0001") is None  # hidden

    # Re-upsert (simulating re-harvest)
    await repo.upsert(_entry(idx=1, score=0.9))

    restored = await repo.get_by_id("pat_0001")
    assert restored is not None
    assert restored["id"] == "pat_0001"
    assert restored["success_metrics"]["weighted_total"] == pytest.approx(0.9)
```

- [ ] **Step 10.3: Create the router**

Create `backend/src/explorator/api/routes/patterns.py`:

```python
"""Pattern library endpoints: list, get, delete, manual harvest."""
from fastapi import APIRouter, Depends, HTTPException, Query

from explorator.api.deps import (
    get_harvest_repos,
    get_pattern_library_repo,
    get_session_repo,
)
from explorator.api.schemas.patterns import (
    CursorResponse,
    HarvestReportResponse,
    PatternItem,
    PatternListResponse,
    SkipEntryResponse,
)
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.graph.session_repo import SessionRepository
from explorator.services.pattern_library.cursor import InvalidCursor, parse_cursor
from explorator.services.pattern_library.filters import PatternFilters
from explorator.services.pattern_library.harvest_service import (
    HarvestRepos,
    harvest_session_finalists,
)

router = APIRouter(tags=["patterns"])


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
    )


@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    genre: str | None = Query(None),
    pattern_type: str | None = Query(None),
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
        filters=PatternFilters(genre=genre, pattern_type=pattern_type),
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


@router.get("/patterns/{entry_id}", response_model=PatternItem)
async def get_pattern(
    entry_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternItem:
    entry = await repo.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="pattern not found")
    return _to_pattern_item(entry)


@router.delete("/patterns/{entry_id}", status_code=204)
async def delete_pattern(
    entry_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> None:
    ok = await repo.soft_delete(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="pattern not found or already deleted")


@router.post(
    "/sessions/{session_id}/finalists/harvest",
    response_model=HarvestReportResponse,
)
async def harvest_session_finalists_endpoint(
    session_id: str,
    repos: HarvestRepos = Depends(get_harvest_repos),  # noqa: B008
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
) -> HarvestReportResponse:
    # 404 if session doesn't exist; 200 + upserted_count=0 if session is empty.
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    report = await harvest_session_finalists(session_id, repos=repos)
    return HarvestReportResponse(
        session_id=report.session_id,
        upserted_count=report.upserted_count,
        skipped_count=report.skipped_count,
        skipped_reasons=[
            SkipEntryResponse(
                candidate_id=e.candidate_id,
                pattern_type=e.pattern_type,
                reason=e.reason.value,
            )
            for e in report.skipped_reasons
        ],
        upserted_pattern_ids=list(report.upserted_pattern_ids),
    )
```

- [ ] **Step 10.4: Register the router in `app.py`**

In `backend/src/explorator/api/app.py`, add the import near the other route imports:

```python
from explorator.api.routes.patterns import router as patterns_router
```

Add the registration after line 70 (`comparisons_router` registration):

```python
    app.include_router(patterns_router, prefix="/v1")
```

- [ ] **Step 10.5: Run the router tests**

Run: `cd backend && uv run pytest tests/api/test_patterns_router.py -v`
Expected: 8 PASS.

- [ ] **Step 10.6: Commit (WIP)**

```bash
git add backend/src/explorator/api/deps.py \
        backend/src/explorator/api/routes/patterns.py \
        backend/src/explorator/api/app.py \
        backend/tests/api/test_patterns_router.py
git commit -m "wip(m5d-2): /v1/patterns router + POST /v1/sessions/{id}/finalists/harvest"
```

---

## Task 11: Install Sonner + mount Toaster + create `lib/toast.ts`

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/lib/toast.ts`

- [ ] **Step 11.1: Install Sonner**

Run: `cd frontend && npm install sonner`
Expected: `sonner` added to `dependencies` in `package.json`, new lockfile entry.

- [ ] **Step 11.2: Create the toast wrapper**

Create `frontend/src/lib/toast.ts`:

```typescript
// Thin wrapper around Sonner so a future swap (or test double) is a one-file change.
// All UI code should import from here, never from 'sonner' directly.
import { toast as sonnerToast, type ExternalToast } from 'sonner';

export type ToastOptions = ExternalToast;

export const toast = {
  success: (message: string, opts?: ToastOptions) => sonnerToast.success(message, opts),
  error: (message: string, opts?: ToastOptions) => sonnerToast.error(message, opts),
  info: (message: string, opts?: ToastOptions) => sonnerToast(message, opts),
};
```

- [ ] **Step 11.3: Mount `<Toaster />` in `App.tsx`**

Replace the existing `frontend/src/App.tsx` contents with:

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Dashboard from './views/Dashboard';
import SessionWorkspace from './views/SessionWorkspace';
import GenreManagement from './components/GenreManagement';
import PatternLibraryBrowser from './views/PatternLibraryBrowser';

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
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  );
}
```

Note: the `PatternLibraryBrowser` view is created in Task 16; the import here will fail until then. That's fine — frontend build runs at the end of the plan.

- [ ] **Step 11.4: Commit (WIP)**

```bash
git add frontend/package.json frontend/package-lock.json \
        frontend/src/App.tsx frontend/src/lib/
git commit -m "wip(m5d-2): install sonner, mount Toaster, add lib/toast wrapper"
```

---

## Task 12: Frontend types mirror + API client

**Files:**
- Create: `frontend/src/api/types.ts` (or merge into existing `services/api.ts`)
- Create: `frontend/src/api/patterns.ts`

- [ ] **Step 12.1: Create the shared types file**

Create `frontend/src/api/types.ts`:

```typescript
// Source of truth: backend/src/explorator/services/pattern_library/harvest_service.py
// If the Pydantic dataclass changes, update this file in the same commit.

export type SkipReason =
  | 'missing_arrangement'
  | 'missing_progression'
  | 'missing_genre'
  | 'no_finalists'
  | 'upsert_failed';

export interface SkipEntry {
  candidate_id: string;
  pattern_type: string;
  reason: SkipReason;
}

export interface HarvestReport {
  session_id: string;
  upserted_count: number;
  skipped_count: number;
  skipped_reasons: SkipEntry[];
  upserted_pattern_ids: string[];
}

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
}
```

- [ ] **Step 12.2: Create the API client**

Create `frontend/src/api/patterns.ts`:

```typescript
import type {
  HarvestReport,
  PatternCursor,
  PatternFilters,
  PatternItem,
  PatternListResponse,
} from './types';

const API_BASE = '/v1';

export async function listPatterns(
  filters: PatternFilters,
  cursor?: PatternCursor,
  limit = 50,
): Promise<PatternListResponse> {
  const params = new URLSearchParams();
  if (filters.genre) params.set('genre', filters.genre);
  if (filters.pattern_type) params.set('pattern_type', filters.pattern_type);
  if (cursor) {
    params.set('after_score', String(cursor.after_score));
    params.set('after_id', cursor.after_id);
  }
  params.set('limit', String(limit));

  const res = await fetch(`${API_BASE}/patterns?${params.toString()}`);
  if (!res.ok) throw new Error(`Failed to list patterns: ${res.status}`);
  return res.json();
}

export async function getPattern(id: string): Promise<PatternItem> {
  const res = await fetch(`${API_BASE}/patterns/${id}`);
  if (!res.ok) throw new Error(`Failed to get pattern: ${res.status}`);
  return res.json();
}

export async function deletePattern(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/patterns/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete pattern: ${res.status}`);
}

export async function harvestSessionFinalists(sessionId: string): Promise<HarvestReport> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/finalists/harvest`,
    { method: 'POST' },
  );
  if (!res.ok) throw new Error(`Failed to harvest finalists: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 12.3: Commit (WIP)**

```bash
git add frontend/src/api/
git commit -m "wip(m5d-2): frontend types mirror + patterns API client"
```

---

## Task 13: Zustand stores (TDD)

**Files:**
- Create: `frontend/src/stores/patternFiltersStore.ts`
- Create: `frontend/src/stores/patternLibraryStore.ts`
- Create: `frontend/src/stores/__tests__/patternFiltersStore.test.ts`
- Create: `frontend/src/stores/__tests__/patternLibraryStore.test.ts`

- [ ] **Step 13.1: Write failing test for filters store**

Create `frontend/src/stores/__tests__/patternFiltersStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { usePatternFiltersStore } from '../patternFiltersStore';

describe('patternFiltersStore', () => {
  beforeEach(() => {
    usePatternFiltersStore.setState({ filters: {} });
  });

  it('setFilter merges a patch into filters', () => {
    usePatternFiltersStore.getState().setFilter({ genre: 'jazz' });
    expect(usePatternFiltersStore.getState().filters).toEqual({ genre: 'jazz' });

    usePatternFiltersStore.getState().setFilter({ pattern_type: 'voicing' });
    expect(usePatternFiltersStore.getState().filters).toEqual({
      genre: 'jazz',
      pattern_type: 'voicing',
    });
  });

  it('setFilter with undefined clears a key', () => {
    usePatternFiltersStore.setState({ filters: { genre: 'jazz' } });
    usePatternFiltersStore.getState().setFilter({ genre: undefined });
    expect(usePatternFiltersStore.getState().filters).toEqual({ genre: undefined });
  });
});
```

- [ ] **Step 13.2: Write failing test for library store**

Create `frontend/src/stores/__tests__/patternLibraryStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { usePatternLibraryStore } from '../patternLibraryStore';
import * as api from '../../api/patterns';
import type { PatternItem, PatternListResponse } from '../../api/types';

const makeItem = (id: string, score: number): PatternItem => ({
  id, pattern_type: 'progression', genre: 'dream_pop', tags: [],
  source_candidate_id: `cand_${id}`, abstracted_pattern: {},
  success_metrics: { weighted_total: score }, notes: '',
  created_at: '2026-04-19T00:00:00Z',
});

describe('patternLibraryStore', () => {
  beforeEach(() => {
    usePatternLibraryStore.getState().reset();
    vi.restoreAllMocks();
  });

  afterEach(() => vi.restoreAllMocks());

  it('loadMore appends items and updates cursor', async () => {
    const response: PatternListResponse = {
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      next_cursor: { after_score: 0.7, after_id: 'p2' },
    };
    vi.spyOn(api, 'listPatterns').mockResolvedValue(response);

    await usePatternLibraryStore.getState().loadMore({});

    const state = usePatternLibraryStore.getState();
    expect(state.items.map((i) => i.id)).toEqual(['p1', 'p2']);
    expect(state.cursor).toEqual({ after_score: 0.7, after_id: 'p2' });
    expect(state.hasMore).toBe(true);
  });

  it('loadMore no-ops when hasMore is false', async () => {
    usePatternLibraryStore.setState({ hasMore: false });
    const spy = vi.spyOn(api, 'listPatterns');

    await usePatternLibraryStore.getState().loadMore({});

    expect(spy).not.toHaveBeenCalled();
  });

  it('loadMore second call terminates when next_cursor is null', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({
      items: [makeItem('p1', 0.8)],
      next_cursor: null,
    });

    await usePatternLibraryStore.getState().loadMore({});

    expect(usePatternLibraryStore.getState().hasMore).toBe(false);
    expect(usePatternLibraryStore.getState().cursor).toBeNull();
  });

  it('removePattern optimistically splices and rolls back on error', async () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      hasMore: true,
    });
    vi.spyOn(api, 'deletePattern').mockRejectedValue(new Error('boom'));

    await expect(
      usePatternLibraryStore.getState().removePattern('p1'),
    ).rejects.toThrow();

    // Rolled back
    expect(
      usePatternLibraryStore.getState().items.map((i) => i.id),
    ).toEqual(['p1', 'p2']);
  });

  it('removePattern commits on success', async () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8), makeItem('p2', 0.7)],
      hasMore: true,
    });
    vi.spyOn(api, 'deletePattern').mockResolvedValue(undefined);

    await usePatternLibraryStore.getState().removePattern('p1');

    expect(
      usePatternLibraryStore.getState().items.map((i) => i.id),
    ).toEqual(['p2']);
  });

  it('reset clears all state', () => {
    usePatternLibraryStore.setState({
      items: [makeItem('p1', 0.8)],
      cursor: { after_score: 0.5, after_id: 'x' },
      hasMore: false,
      loading: true,
      error: 'err',
    });

    usePatternLibraryStore.getState().reset();

    const state = usePatternLibraryStore.getState();
    expect(state.items).toEqual([]);
    expect(state.cursor).toBeNull();
    expect(state.hasMore).toBe(true);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });
});
```

- [ ] **Step 13.3: Run the tests to confirm they fail**

Run: `cd frontend && npm run test:unit -- --run stores/__tests__/`
Expected: FAIL (stores don't exist yet).

- [ ] **Step 13.4: Implement the filters store**

Create `frontend/src/stores/patternFiltersStore.ts`:

```typescript
import { create } from 'zustand';
import type { PatternFilters } from '../api/types';

interface PatternFiltersState {
  filters: PatternFilters;
  setFilter: (patch: PatternFilters) => void;
}

export const usePatternFiltersStore = create<PatternFiltersState>((set) => ({
  filters: {},
  setFilter: (patch) => set((state) => ({ filters: { ...state.filters, ...patch } })),
}));
```

- [ ] **Step 13.5: Implement the library store**

Create `frontend/src/stores/patternLibraryStore.ts`:

```typescript
import { create } from 'zustand';
import { listPatterns, deletePattern } from '../api/patterns';
import type { PatternCursor, PatternFilters, PatternItem } from '../api/types';

interface PatternLibraryState {
  items: PatternItem[];
  cursor: PatternCursor | null;
  hasMore: boolean;
  loading: boolean;
  error: string | null;

  loadMore: (filters: PatternFilters) => Promise<void>;
  removePattern: (id: string) => Promise<void>;
  reset: () => void;
}

const INITIAL: Omit<PatternLibraryState, 'loadMore' | 'removePattern' | 'reset'> = {
  items: [],
  cursor: null,
  hasMore: true,
  loading: false,
  error: null,
};

export const usePatternLibraryStore = create<PatternLibraryState>((set, get) => ({
  ...INITIAL,

  loadMore: async (filters) => {
    if (!get().hasMore || get().loading) return;
    set({ loading: true, error: null });
    try {
      const response = await listPatterns(filters, get().cursor ?? undefined);
      set((state) => ({
        items: [...state.items, ...response.items],
        cursor: response.next_cursor,
        hasMore: response.next_cursor !== null,
        loading: false,
      }));
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : String(err) });
    }
  },

  removePattern: async (id) => {
    const prevItems = get().items;
    set({ items: prevItems.filter((p) => p.id !== id) });
    try {
      await deletePattern(id);
    } catch (err) {
      set({ items: prevItems, error: err instanceof Error ? err.message : String(err) });
      throw err;
    }
  },

  reset: () => set({ ...INITIAL }),
}));
```

- [ ] **Step 13.6: Run the tests**

Run: `cd frontend && npm run test:unit -- --run stores/__tests__/`
Expected: all tests PASS.

- [ ] **Step 13.7: Commit (WIP)**

```bash
git add frontend/src/stores/
git commit -m "wip(m5d-2): patternFiltersStore + patternLibraryStore (Zustand)"
```

---

## Task 14: PatternCard, PatternFilters, PatternList, LoadMoreButton, EmptyState components

**Files:**
- Create: `frontend/src/components/patterns/PatternCard.tsx`
- Create: `frontend/src/components/patterns/PatternFilters.tsx`
- Create: `frontend/src/components/patterns/PatternList.tsx`
- Create: `frontend/src/components/patterns/LoadMoreButton.tsx`
- Create: `frontend/src/components/patterns/EmptyState.tsx`

- [ ] **Step 14.1: `PatternCard.tsx`**

```typescript
import type { PatternItem } from '../../api/types';

interface Props {
  pattern: PatternItem;
  onDelete: (id: string) => void;
}

function shortHash(id: string): string {
  return id.length > 8 ? id.slice(-8) : id;
}

export function PatternCard({ pattern, onDelete }: Props) {
  const score = pattern.success_metrics.weighted_total ?? 0;
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

- [ ] **Step 14.2: `PatternFilters.tsx`**

```typescript
import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

const PATTERN_TYPES = ['progression', 'voicing', 'bass', 'groove', 'melody'] as const;

export function PatternFilters() {
  const filters = usePatternFiltersStore((s) => s.filters);
  const setFilter = usePatternFiltersStore((s) => s.setFilter);

  return (
    <div className="flex gap-3 mb-4" data-testid="pattern-filters">
      <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        Genre:
        <input
          type="text"
          value={filters.genre ?? ''}
          onChange={(e) => setFilter({ genre: e.target.value || undefined })}
          placeholder="all"
          className="px-2 py-1 rounded"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
        />
      </label>
      <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
        Type:
        <select
          value={filters.pattern_type ?? ''}
          onChange={(e) => setFilter({ pattern_type: e.target.value || undefined })}
          className="px-2 py-1 rounded"
          style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
        >
          <option value="">all</option>
          {PATTERN_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
```

- [ ] **Step 14.3: `PatternList.tsx`**

```typescript
import { PatternCard } from './PatternCard';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { toast } from '../../lib/toast';

export function PatternList() {
  const items = usePatternLibraryStore((s) => s.items);
  const removePattern = usePatternLibraryStore((s) => s.removePattern);

  const handleDelete = async (id: string) => {
    try {
      await removePattern(id);
      toast.success('Pattern deleted');
    } catch {
      toast.error('Failed to delete pattern');
    }
  };

  return (
    <div className="flex flex-col gap-2" data-testid="pattern-list">
      {items.map((p) => (
        <PatternCard key={p.id} pattern={p} onDelete={handleDelete} />
      ))}
    </div>
  );
}
```

- [ ] **Step 14.4: `LoadMoreButton.tsx`**

```typescript
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

export function LoadMoreButton() {
  const hasMore = usePatternLibraryStore((s) => s.hasMore);
  const loading = usePatternLibraryStore((s) => s.loading);
  const loadMore = usePatternLibraryStore((s) => s.loadMore);
  const filters = usePatternFiltersStore((s) => s.filters);

  if (!hasMore) return null;

  return (
    <button
      onClick={() => loadMore(filters)}
      disabled={loading}
      data-testid="load-more-button"
      className="mt-4 px-4 py-2 rounded disabled:opacity-30"
      style={{ background: 'var(--surface-2)', color: 'var(--text-primary)' }}
    >
      {loading ? 'Loading...' : 'Load more'}
    </button>
  );
}
```

- [ ] **Step 14.5: `EmptyState.tsx`**

```typescript
export function EmptyState() {
  return (
    <div
      data-testid="empty-state"
      className="text-center py-12 text-sm"
      style={{ color: 'var(--text-muted)' }}
    >
      No patterns yet. Run a session and save its finalists to start your library.
    </div>
  );
}
```

- [ ] **Step 14.6: Commit (WIP)**

```bash
git add frontend/src/components/patterns/
git commit -m "wip(m5d-2): PatternCard, PatternFilters, PatternList, LoadMoreButton, EmptyState"
```

---

## Task 15: `PatternLibraryBrowser` view + nav link

**Files:**
- Create: `frontend/src/views/PatternLibraryBrowser.tsx`
- Modify: `frontend/src/views/Dashboard.tsx`

- [ ] **Step 15.1: Create the view**

```typescript
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { PatternFilters } from '../components/patterns/PatternFilters';
import { PatternList } from '../components/patterns/PatternList';
import { LoadMoreButton } from '../components/patterns/LoadMoreButton';
import { EmptyState } from '../components/patterns/EmptyState';
import { usePatternFiltersStore } from '../stores/patternFiltersStore';
import { usePatternLibraryStore } from '../stores/patternLibraryStore';

export default function PatternLibraryBrowser() {
  const filters = usePatternFiltersStore((s) => s.filters);
  const items = usePatternLibraryStore((s) => s.items);
  const loading = usePatternLibraryStore((s) => s.loading);
  const reset = usePatternLibraryStore((s) => s.reset);
  const loadMore = usePatternLibraryStore((s) => s.loadMore);

  // Reset + refetch when filters change
  useEffect(() => {
    reset();
    void loadMore(filters);
  }, [filters.genre, filters.pattern_type, reset, loadMore]);

  const showEmpty = !loading && items.length === 0;

  return (
    <div className="min-h-screen px-8 py-12">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-light" style={{ color: 'var(--text-primary)' }}>
            Pattern Library
          </h1>
          <Link
            to="/"
            className="text-xs tracking-wider uppercase"
            style={{ color: 'var(--text-muted)' }}
          >
            &larr; Dashboard
          </Link>
        </div>
        <PatternFilters />
        {showEmpty ? <EmptyState /> : <PatternList />}
        <LoadMoreButton />
      </div>
    </div>
  );
}
```

- [ ] **Step 15.2: Add the Library nav link on Dashboard**

In `frontend/src/views/Dashboard.tsx`, find the existing "Manage Genres →" block (around lines 40-50) and add a sibling link:

```tsx
<div className="mt-4 flex gap-4 justify-center">
  <a
    href="/genres"
    className="text-xs tracking-wider uppercase transition-colors"
    style={{ color: 'var(--text-muted)' }}
    onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
    onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
  >
    Manage Genres &rarr;
  </a>
  <a
    href="/patterns"
    className="text-xs tracking-wider uppercase transition-colors"
    style={{ color: 'var(--text-muted)' }}
    onMouseOver={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
    onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
  >
    Pattern Library &rarr;
  </a>
</div>
```

- [ ] **Step 15.3: Build-check the frontend**

Run: `cd frontend && npm run build`
Expected: clean build with no TypeScript errors.

- [ ] **Step 15.4: Commit (WIP)**

```bash
git add frontend/src/views/
git commit -m "wip(m5d-2): PatternLibraryBrowser view + Dashboard nav link"
```

---

## Task 16: `useRealizationFlow` — `harvest_patterns` SSE toast

**Files:**
- Modify: `frontend/src/hooks/useRealizationFlow.ts:91-96`

- [ ] **Step 16.1: Add the harvest-completed case**

In `frontend/src/hooks/useRealizationFlow.ts`, find the SSE event dispatch block (around lines 91-95) and extend it:

```typescript
          if (!dataStr) continue;
          try {
            const data = JSON.parse(dataStr);
            const node = data.node as string | undefined;
            if (eventType === 'node_started' && node) setCurrentNode(node);
            else if (eventType === 'node_completed' && node === 'harvest_patterns') {
              const count = (data.count as number) ?? 0;
              toast.success(`Saved ${count} patterns to library`);
            }
            else if (eventType === 'realization_completed') setCurrentNode(null);
          } catch { /* skip */ }
```

Add the import at the top of the file:

```typescript
import { toast } from '../lib/toast';
```

- [ ] **Step 16.2: Commit (WIP)**

```bash
git add frontend/src/hooks/useRealizationFlow.ts
git commit -m "wip(m5d-2): toast on harvest_patterns node_completed SSE event"
```

---

## Task 17: FinalistPanel — "Save finalists to library" button

**Files:**
- Modify: `frontend/src/components/FinalistPanel.tsx`

- [ ] **Step 17.1: Accept `sessionId` prop and add the button**

Update `frontend/src/components/FinalistPanel.tsx`:

Replace the `interface FinalistPanelProps` block with:

```typescript
interface FinalistPanelProps {
  finalSelection: FinalSelection;
  arrangements: ArrangementSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sessionId: string;
}
```

Add imports at the top of the file:

```typescript
import { useState } from 'react';
import { harvestSessionFinalists } from '../api/patterns';
import { toast } from '../lib/toast';
```

Update the function signature and body. Replace the destructure and early return with:

```typescript
export default function FinalistPanel({
  finalSelection,
  arrangements,
  selectedId,
  onSelect,
  sessionId,
}: FinalistPanelProps) {
  const [saving, setSaving] = useState(false);
  const { selection_roles, selected_candidate_ids } = finalSelection;
  if (selected_candidate_ids.length === 0) return null;

  const handleSave = async () => {
    setSaving(true);
    try {
      const report = await harvestSessionFinalists(sessionId);
      toast.success(`Saved ${report.upserted_count} patterns to library`);
    } catch {
      toast.error('Failed to save finalists');
    } finally {
      setSaving(false);
    }
  };

  const arrLookup = new Map(arrangements.map((a) => [a.id, a]));
```

Insert the button after the header section (inside the first `<div className="px-3 py-2">` block's flex container). Replace lines 35-48 with:

```tsx
      <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center justify-between">
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
          <button
            onClick={handleSave}
            disabled={saving}
            data-testid="save-finalists-to-library"
            className="text-xs px-2 py-1 rounded disabled:opacity-30"
            style={{ background: 'var(--surface-3)', color: 'var(--text-primary)' }}
          >
            {saving ? 'Saving...' : 'Save to library'}
          </button>
        </div>
      </div>
```

- [ ] **Step 17.2: Update the FinalistPanel caller to pass `sessionId`**

Run: `cd frontend && grep -rn "FinalistPanel" src/`

Find the usage (likely in `SessionWorkspace.tsx`) and update the JSX to pass `sessionId={sessionId}` — the session id is already available via `useParams()` in that view.

- [ ] **Step 17.3: Build-check**

Run: `cd frontend && npm run build`
Expected: green.

- [ ] **Step 17.4: Commit (WIP)**

```bash
git add frontend/src/components/FinalistPanel.tsx frontend/src/views/
git commit -m "wip(m5d-2): FinalistPanel Save to library button"
```

---

## Task 18: Component tests for PatternCard + PatternLibraryBrowser + FinalistPanel button

**Files:**
- Create: `frontend/src/components/patterns/__tests__/PatternCard.test.tsx`
- Create: `frontend/src/views/__tests__/PatternLibraryBrowser.test.tsx`
- Create: `frontend/src/components/__tests__/FinalistPanel.test.tsx`

- [ ] **Step 18.1: `PatternCard.test.tsx`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PatternCard } from '../PatternCard';
import type { PatternItem } from '../../../api/types';

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
};

describe('PatternCard', () => {
  it('renders type, genre, score, short-hash source, tags, notes', () => {
    render(<PatternCard pattern={item} onDelete={vi.fn()} />);
    expect(screen.getByText('progression')).toBeInTheDocument();
    expect(screen.getByText('jazz')).toBeInTheDocument();
    expect(screen.getByText('0.87')).toBeInTheDocument();
    expect(screen.getByText(/cand_0001_xyz/)).toBeInTheDocument(); // short hash shows suffix
    expect(screen.getByText('role:safest')).toBeInTheDocument();
    expect(screen.getByText('ii-V-I with tritone sub')).toBeInTheDocument();
  });

  it('calls onDelete when confirmed', () => {
    const onDelete = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<PatternCard pattern={item} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText('Delete pat_0001'));
    expect(onDelete).toHaveBeenCalledWith('pat_0001');
  });

  it('does not call onDelete when cancelled', () => {
    const onDelete = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PatternCard pattern={item} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText('Delete pat_0001'));
    expect(onDelete).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 18.2: `PatternLibraryBrowser.test.tsx`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PatternLibraryBrowser from '../PatternLibraryBrowser';
import * as api from '../../api/patterns';
import { usePatternLibraryStore } from '../../stores/patternLibraryStore';
import { usePatternFiltersStore } from '../../stores/patternFiltersStore';

beforeEach(() => {
  usePatternLibraryStore.getState().reset();
  usePatternFiltersStore.setState({ filters: {} });
  vi.restoreAllMocks();
});

describe('PatternLibraryBrowser', () => {
  it('shows empty state when no items', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({ items: [], next_cursor: null });

    render(<MemoryRouter><PatternLibraryBrowser /></MemoryRouter>);

    await waitFor(() => expect(screen.getByTestId('empty-state')).toBeInTheDocument());
  });

  it('renders pattern list when items exist', async () => {
    vi.spyOn(api, 'listPatterns').mockResolvedValue({
      items: [{
        id: 'pat_0001', pattern_type: 'progression', genre: 'jazz',
        tags: [], source_candidate_id: 'c', abstracted_pattern: {},
        success_metrics: { weighted_total: 0.8 }, notes: '',
        created_at: '2026-04-19T00:00:00Z',
      }],
      next_cursor: null,
    });

    render(<MemoryRouter><PatternLibraryBrowser /></MemoryRouter>);

    await waitFor(() => expect(screen.getByTestId('pattern-card-pat_0001')).toBeInTheDocument());
    expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 18.3: `FinalistPanel.test.tsx`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import FinalistPanel from '../FinalistPanel';
import * as patternsApi from '../../api/patterns';
import type { ArrangementSummary, FinalSelection } from '../../services/api';

const finalSelection: FinalSelection = {
  selected_candidate_ids: ['arr_01'],
  selection_roles: { arr_01: 'safest' },
  selection_notes: [],
};

const arrangements: ArrangementSummary[] = [{
  id: 'arr_01', weighted_total: 0.8, rationale: 'test',
  // ... other required ArrangementSummary fields
} as ArrangementSummary];

beforeEach(() => vi.restoreAllMocks());

describe('FinalistPanel Save to library button', () => {
  it('fires harvestSessionFinalists and shows success toast', async () => {
    const spy = vi.spyOn(patternsApi, 'harvestSessionFinalists').mockResolvedValue({
      session_id: 'sess_01',
      upserted_count: 5,
      skipped_count: 0,
      skipped_reasons: [],
      upserted_pattern_ids: [],
    });

    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_01"
      />,
    );

    fireEvent.click(screen.getByTestId('save-finalists-to-library'));

    await waitFor(() => expect(spy).toHaveBeenCalledWith('sess_01'));
  });

  it('disables button while saving', async () => {
    vi.spyOn(patternsApi, 'harvestSessionFinalists').mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        session_id: 'sess_01', upserted_count: 0, skipped_count: 0,
        skipped_reasons: [], upserted_pattern_ids: [],
      }), 100)),
    );

    render(
      <FinalistPanel
        finalSelection={finalSelection}
        arrangements={arrangements}
        selectedId={null}
        onSelect={vi.fn()}
        sessionId="sess_01"
      />,
    );

    const button = screen.getByTestId('save-finalists-to-library') as HTMLButtonElement;
    fireEvent.click(button);

    expect(button.disabled).toBe(true);
  });
});
```

- [ ] **Step 18.4: Run frontend tests**

Run: `cd frontend && npm run test:unit`
Expected: green. If `ArrangementSummary` has more required fields, fill them in the test fixture minimally.

- [ ] **Step 18.5: Commit (WIP)**

```bash
git add frontend/src/components/patterns/__tests__/ \
        frontend/src/views/__tests__/ \
        frontend/src/components/__tests__/
git commit -m "wip(m5d-2): component and view tests for pattern library UI"
```

---

## Task 19: E2E — pattern library round-trip

**Files:**
- Create: `e2e/tests/pattern-library.spec.ts`

- [ ] **Step 19.1: Write the E2E spec**

```typescript
import { test, expect, goToWorkspace, generateCandidates, realizeFirstCandidate } from '../fixtures/test-fixtures';

test.describe('Pattern Library', () => {
  test('session finalists appear in library and can be deleted', async ({ page, testSession }) => {
    // 1. Create + complete a session (finalists are selected by the realization pipeline)
    await goToWorkspace(page, testSession.sessionId);
    await generateCandidates(page, testSession.prompt);
    await realizeFirstCandidate(page);

    // 2. Wait for Sonner's "Saved N patterns to library" toast from the harvest_patterns node
    const savedToast = page.locator('text=/Saved \\d+ patterns to library/');
    await expect(savedToast.first()).toBeVisible({ timeout: 60_000 });

    // 3. Navigate to the library and read the count
    await page.goto('/patterns');
    const firstCard = page.locator('[data-testid^="pattern-card-"]').first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });

    const cardsBefore = await page.locator('[data-testid^="pattern-card-"]').count();
    expect(cardsBefore).toBeGreaterThan(0);

    // 4. Delete one card
    page.once('dialog', (dialog) => dialog.accept()); // confirm() dialog
    await firstCard.getByRole('button', { name: /delete/i }).click();

    // 5. Assert list length decremented
    await expect.poll(
      async () => page.locator('[data-testid^="pattern-card-"]').count(),
    ).toBe(cardsBefore - 1);

    // 6. Reload; deleted row does not reappear (soft-delete persisted)
    await page.reload();
    await expect.poll(
      async () => page.locator('[data-testid^="pattern-card-"]').count(),
    ).toBe(cardsBefore - 1);
  });
});
```

- [ ] **Step 19.2: Run the E2E (with stack running)**

Prerequisite: backend + frontend + Neo4j running locally.

Run: `cd e2e && npx playwright test tests/pattern-library.spec.ts --project=chromium`
Expected: PASS. If selectors need adjusting per the actual DOM (e.g. the realization button label), update the test.

- [ ] **Step 19.3: Commit (WIP)**

```bash
git add e2e/tests/pattern-library.spec.ts
git commit -m "wip(m5d-2): E2E — create session, verify library, delete, reload persists"
```

---

## Task 20: Full test run + build checks

- [ ] **Step 20.1: Backend full suite**

Run: `cd backend && uv run pytest -q`
Expected: green.

- [ ] **Step 20.2: Frontend full suite**

Run: `cd frontend && npm run test:unit`
Expected: green.

- [ ] **Step 20.3: Frontend build**

Run: `cd frontend && npm run build`
Expected: green, no TypeScript errors.

- [ ] **Step 20.4: If anything fails, fix it**

Do not proceed to the squash until all three are green.

---

## Task 21: Squash WIPs into Commit B

- [ ] **Step 21.1: Identify the boundary**

The first Commit B WIP is Task 4 (`add deleted_at column + upsert clears it unconditionally`). Commit A is the last non-WIP commit.

- [ ] **Step 21.2: Squash**

```bash
git log --oneline | head -30   # confirm the boundary
# count the WIP commits from Task 4 through Task 19 (~16-18 WIP commits)
```

Reset softly to Commit A's parent-of-B, then commit everything as Commit B:

```bash
# Use `git rebase -i` in this specific case — but the user's project rules say
# "never use -i". Instead, use soft-reset-and-recommit. The SHA here is the
# Commit A hash; find it with `git log --oneline` — it's the commit matching
# "refactor(m5d-2): extract harvest orchestration...".
git reset --soft <COMMIT_A_SHA>
git commit -m "$(cat <<'EOF'
feat(m5d-2): pattern library browser — API, UI, soft-delete

Builds on Commit A's harvest helper extraction.

Backend:
- Model: PatternLibraryEntry gains deleted_at; upsert clears it unconditionally
  on MATCH; natural key (source_candidate_id, pattern_type) unchanged.
- Repo: list_page (keyset-paginated, compound tiebreaker on weighted_total+id),
  iter_all (unbounded internal generator), soft_delete, get_by_id now hides
  deleted rows. list_all removed; query_for_warm_starts migrated to iter_all.
- Services: cursor.py (parse_cursor, Cursor, InvalidCursor), filters.py
  (PatternFilters dataclass), harvest_service.py adds public
  harvest_session_finalists(session_id, repos) entry point.
- API: new /v1/patterns router — list, get, delete endpoints plus
  POST /v1/sessions/{id}/finalists/harvest. Plaintext cursor query params
  (after_score, after_id). Pydantic schemas drop embedding and deleted_at.
- Migration: m5d2_pattern_library_indexes creates composite sort index on
  (:PatternLibraryEntry {weighted_total, id}).
- Tests: keyset pagination + tiebreaker + soft-delete + resurrection + cursor
  codec + router happy/404/400 paths.

Frontend:
- Install Sonner; <Toaster /> mounted in App.tsx; thin lib/toast wrapper.
- New /patterns route + PatternLibraryBrowser view composing PatternFilters,
  PatternList, LoadMoreButton, EmptyState, PatternCard.
- Two Zustand stores (patternFiltersStore, patternLibraryStore) with reset
  semantics distinct from pagination semantics.
- api/patterns.ts client; api/types.ts mirrors backend HarvestReport.
- useRealizationFlow emits toast on node_completed(harvest_patterns).
- FinalistPanel gains a "Save to library" button.
- Dashboard has a Pattern Library nav link.

E2E:
- e2e/tests/pattern-library.spec.ts exercises the full round-trip.

Spec: docs/design/specs/2026-04-19-m5d2-library-browser-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 21.3: Verify the log**

Run: `git log --oneline | head -5`
Expected: two new commits — Commit A (refactor) and Commit B (feat).

- [ ] **Step 21.4: Final sanity check**

Run: `cd backend && uv run pytest -q && cd ../frontend && npm run test:unit && npm run build`
Expected: green on all three.

---

## Summary

**Commit A** (Tasks 1–3): Pure extraction of harvest orchestration into `services/pattern_library/harvest_service.py`. No external behavior change; existing `test_m5d1_harvest.py` passes unchanged.

**Commit B** (Tasks 4–21): Pattern library API, soft-delete schema addition, keyset-paginated repo methods, cursor module, Pydantic schemas, `/patterns` router, public `harvest_session_finalists` entry point, Sonner toasts, two Zustand stores, pattern browser UI components + view, Dashboard nav link, SSE toast in `useRealizationFlow`, FinalistPanel "Save to library" button, E2E spec.

**Preflight verified pre-plan:** `test_m5d1_harvest.py` assertions are field-subset; no narrowing commit needed before Commit A.

