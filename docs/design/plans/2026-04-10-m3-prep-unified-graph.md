# M3-prep: Unified Graph & State — Implementation Plan


**Goal:** Merge the separate M1 and M2 LangGraph pipelines into a single unified graph with one state type, enabling M3's mutation loop to route conditionally to any point in the pipeline.

**Architecture:** Replace `ExplorationState` (M1, 11 fields) + `RealizationState` (M2, 10 fields) with a single `ExplorationState` containing all fields. Replace `build_m1_graph()` + `build_realization_graph()` with `build_exploration_graph()` wiring all 14 nodes linearly. Update all M2 node type annotations from `RealizationState` → `ExplorationState`. Update API routes to use the unified graph. Keep the separate realization endpoint for independent re-realization.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, Neo4j, pytest, mypy

**Spec:** `docs/design/specs/2026-04-10-m3-guided-search-design.md` — Section 2

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/src/explorator/engine/state.py` | Add RealizationState fields to ExplorationState |
| Modify | `backend/src/explorator/engine/realization_state.py` | Re-export alias → delete |
| Modify | `backend/src/explorator/engine/graph.py` | New `build_exploration_graph()` with all 14 nodes |
| Delete | `backend/src/explorator/engine/realization_graph.py` | Replaced by unified graph |
| Modify | `backend/src/explorator/engine/nodes/load_context.py` | RealizationState → ExplorationState; skip fetch when state populated |
| Modify | `backend/src/explorator/engine/nodes/plan_voicings.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/engine/nodes/generate_bass.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/engine/nodes/assemble_arrangements.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/engine/nodes/evaluate_arrangements.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/engine/nodes/rank_and_select.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/engine/nodes/persist_realization.py` | RealizationState → ExplorationState |
| Modify | `backend/src/explorator/api/routes/rounds.py` | Use `build_exploration_graph` |
| Modify | `backend/src/explorator/api/routes/realization_rounds.py` | Use `build_exploration_graph` (subset entry) |
| Modify | `backend/tests/unit/engine/test_state.py` | Test new fields |
| Create | `backend/tests/unit/engine/test_unified_graph.py` | Test graph compilation + node presence |
| Modify | `backend/tests/integration/test_realization_flow.py` | Update imports |

---

### Task 1: Expand ExplorationState with Realization Fields

**Files:**
- Modify: `backend/src/explorator/engine/state.py`
- Test: `backend/tests/unit/engine/test_state.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/engine/test_state.py`:

```python
def test_exploration_state_includes_realization_fields() -> None:
    """Unified state supports all M2 realization fields."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "Dream pop",
        "progression_candidate_ids": ["pc_01", "pc_02"],
        "voicing_strategies": [{"type": "open"}],
        "voicing_plans": [{"id": "vp_01"}],
        "bass_lines": [{"id": "bl_01"}],
        "arrangement_candidates": [{"id": "arr_01"}],
        "arrangement_families": [{"id": "fam_01"}],
        "selected_arrangements": [{"id": "arr_01"}],
    }
    assert state["progression_candidate_ids"] == ["pc_01", "pc_02"]
    assert len(state["voicing_plans"]) == 1
    assert len(state["arrangement_candidates"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/engine/test_state.py::test_exploration_state_includes_realization_fields -v`
Expected: FAIL — TypedDict does not have `progression_candidate_ids` key

- [ ] **Step 3: Add realization fields to ExplorationState**

Edit `backend/src/explorator/engine/state.py` — add after the `scorecards` field:

```python
    # --- Realization (merged from RealizationState) ---
    progression_candidate_ids: list[str]
    voicing_strategies: list[dict[str, Any]]
    voicing_plans: list[dict[str, Any]]
    bass_lines: list[dict[str, Any]]
    arrangement_candidates: list[dict[str, Any]]
    arrangement_families: list[dict[str, Any]]
    selected_arrangements: list[dict[str, Any]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/engine/test_state.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add src/explorator/engine/state.py tests/unit/engine/test_state.py
git commit -m "feat(m3-prep): add realization fields to ExplorationState"
```

---

### Task 2: Update RealizationState to Re-export Alias

**Files:**
- Modify: `backend/src/explorator/engine/realization_state.py`

- [ ] **Step 1: Replace RealizationState with alias**

Replace the entire contents of `backend/src/explorator/engine/realization_state.py` with:

```python
"""Backwards-compatible alias — RealizationState is now ExplorationState.

This file exists temporarily so existing imports don't break.
It will be removed once all M2 nodes are updated to import ExplorationState directly.
"""

from explorator.engine.state import ExplorationState

RealizationState = ExplorationState
```

- [ ] **Step 2: Run all existing tests to verify nothing breaks**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All existing tests PASS (the alias means all M2 node imports still resolve)

- [ ] **Step 3: Commit**

```bash
cd backend && git add src/explorator/engine/realization_state.py
git commit -m "refactor(m3-prep): make RealizationState an alias for ExplorationState"
```

---

### Task 3: Update M2 Node Imports — load_context

**Files:**
- Modify: `backend/src/explorator/engine/nodes/load_context.py`

- [ ] **Step 1: Update import and signature**

In `backend/src/explorator/engine/nodes/load_context.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from:

```python
async def load_context(state: RealizationState, *, driver: AsyncDriver) -> dict[str, Any]:
```

to:

```python
async def load_context(state: ExplorationState, *, driver: AsyncDriver) -> dict[str, Any]:
```

- [ ] **Step 2: Add skip-when-populated logic**

At the top of the `load_context` function body, after the progress callback, add:

```python
    # In unified graph, state may already have these fields from M1 pipeline.
    # Skip Neo4j fetch when data is already present (e.g., during mutation loop re-entry).
    if state.get("progression_candidates") and state.get("genre_profile"):
        return {}
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd backend && git add src/explorator/engine/nodes/load_context.py
git commit -m "refactor(m3-prep): update load_context to ExplorationState with skip-when-populated"
```

---

### Task 4: Update M2 Node Imports — plan_voicings, generate_bass, assemble_arrangements

**Files:**
- Modify: `backend/src/explorator/engine/nodes/plan_voicings.py`
- Modify: `backend/src/explorator/engine/nodes/generate_bass.py`
- Modify: `backend/src/explorator/engine/nodes/assemble_arrangements.py`

- [ ] **Step 1: Update plan_voicings.py**

In `backend/src/explorator/engine/nodes/plan_voicings.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 2: Update generate_bass.py**

In `backend/src/explorator/engine/nodes/generate_bass.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 3: Update assemble_arrangements.py**

In `backend/src/explorator/engine/nodes/assemble_arrangements.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add src/explorator/engine/nodes/plan_voicings.py src/explorator/engine/nodes/generate_bass.py src/explorator/engine/nodes/assemble_arrangements.py
git commit -m "refactor(m3-prep): update plan_voicings, generate_bass, assemble to ExplorationState"
```

---

### Task 5: Update M2 Node Imports — evaluate_arrangements, rank_and_select, persist_realization

**Files:**
- Modify: `backend/src/explorator/engine/nodes/evaluate_arrangements.py`
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Modify: `backend/src/explorator/engine/nodes/persist_realization.py`

- [ ] **Step 1: Update evaluate_arrangements.py**

In `backend/src/explorator/engine/nodes/evaluate_arrangements.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 2: Update rank_and_select.py**

In `backend/src/explorator/engine/nodes/rank_and_select.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 3: Update persist_realization.py**

In `backend/src/explorator/engine/nodes/persist_realization.py`, change:

```python
from explorator.engine.realization_state import RealizationState
```

to:

```python
from explorator.engine.state import ExplorationState
```

And change the function signature from `state: RealizationState` to `state: ExplorationState`.

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add src/explorator/engine/nodes/evaluate_arrangements.py src/explorator/engine/nodes/rank_and_select.py src/explorator/engine/nodes/persist_realization.py
git commit -m "refactor(m3-prep): update evaluate_arrangements, rank_and_select, persist_realization to ExplorationState"
```

---

### Task 6: Build Unified Exploration Graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Create: `backend/tests/unit/engine/test_unified_graph.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/engine/test_unified_graph.py`:

```python
"""Tests for the unified exploration graph."""

from unittest.mock import MagicMock

from explorator.engine.graph import build_exploration_graph, build_realization_subgraph


def test_exploration_graph_compiles() -> None:
    """Unified graph compiles with mock dependencies."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    assert graph is not None


def test_exploration_graph_has_all_nodes() -> None:
    """Unified graph contains all M1+M2 nodes."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    node_names = set(graph.nodes.keys())
    expected = {
        "parse_intent",
        "load_genre",
        "generate",
        "evaluate_progressions",
        "select_top_progressions",
        "load_context",
        "plan_voicings",
        "generate_bass",
        "assemble",
        "evaluate_arrangements",
        "rank_and_select",
        "persist_realization",
        "persist_round",
    }
    missing = expected - node_names
    assert not missing, f"Missing nodes: {missing}"


def test_exploration_graph_entry_point() -> None:
    """Graph starts at parse_intent."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    # LangGraph compiled graph has __start__ → first node
    assert "__start__" in graph.nodes or "parse_intent" in graph.nodes


def test_realization_subgraph_compiles() -> None:
    """Realization subgraph compiles with mock dependencies."""
    graph = build_realization_subgraph(MagicMock(), MagicMock())
    assert graph is not None


def test_realization_subgraph_has_m2_nodes() -> None:
    """Realization subgraph contains only M2 nodes."""
    graph = build_realization_subgraph(MagicMock(), MagicMock())
    node_names = set(graph.nodes.keys())
    expected = {
        "load_context",
        "plan_voicings",
        "generate_bass",
        "assemble",
        "evaluate_arrangements",
        "rank_and_select",
        "persist_realization",
    }
    missing = expected - node_names
    assert not missing, f"Missing nodes: {missing}"
    # Should NOT contain M1 nodes
    assert "parse_intent" not in node_names
    assert "generate" not in node_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/engine/test_unified_graph.py -v`
Expected: FAIL — `build_exploration_graph` does not exist (only `build_m1_graph`)

- [ ] **Step 3: Implement unified graph**

Replace the entire contents of `backend/src/explorator/engine/graph.py`:

```python
"""LangGraph unified exploration graph — M1 + M2 pipeline.

Full flow: parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble → evaluate_arrangements
  → rank_and_select → persist_realization → persist_round → END
"""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.assemble_arrangements import assemble_arrangements
from explorator.engine.nodes.evaluate_arrangements import evaluate_arrangements
from explorator.engine.nodes.evaluate_progressions import evaluate_progressions
from explorator.engine.nodes.generate import generate
from explorator.engine.nodes.generate_bass import generate_bass
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.load_genre import load_genre
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.persist_round import persist_round
from explorator.engine.nodes.plan_voicings import plan_voicings
from explorator.engine.nodes.rank_and_select import rank_and_select
from explorator.engine.nodes.select_top_progressions import select_top_progressions
from explorator.engine.state import ExplorationState


def build_exploration_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the unified M1+M2 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # M1 nodes
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)

    # M2 nodes
    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))

    # Persistence
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Linear flow: M1 → M2 → persist
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "load_context")
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile(recursion_limit=100)


def build_realization_subgraph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build M2-only subgraph for independent realization (used by realization endpoint)."""
    graph = StateGraph(ExplorationState)

    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", END)

    return graph.compile(recursion_limit=100)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/engine/test_unified_graph.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: Existing M1 tests that import `build_m1_graph` will FAIL — we fix that in the next task.

- [ ] **Step 6: Commit**

```bash
cd backend && git add src/explorator/engine/graph.py tests/unit/engine/test_unified_graph.py
git commit -m "feat(m3-prep): unified exploration graph with all 14 nodes and recursion_limit=100"
```

---

### Task 7: Provide Backwards-Compatible build_m1_graph Alias

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`

Any code that imports `build_m1_graph` needs to keep working until callers are updated.

- [ ] **Step 1: Add alias at the bottom of graph.py**

Add at the end of `backend/src/explorator/engine/graph.py`:

```python
# Backwards-compatible alias — will be removed after M3-prep completes
build_m1_graph = build_exploration_graph
```

- [ ] **Step 2: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS (callers of `build_m1_graph` resolve via alias)

- [ ] **Step 3: Commit**

```bash
cd backend && git add src/explorator/engine/graph.py
git commit -m "refactor(m3-prep): add build_m1_graph alias for backwards compatibility"
```

---

### Task 8: Update API Route — rounds.py

**Files:**
- Modify: `backend/src/explorator/api/routes/rounds.py`

- [ ] **Step 1: Update import**

In `backend/src/explorator/api/routes/rounds.py`, change:

```python
from explorator.engine.graph import build_m1_graph
```

to:

```python
from explorator.engine.graph import build_exploration_graph
```

- [ ] **Step 2: Update graph call**

In the `trigger_round` function, change:

```python
graph = build_m1_graph(gemini, driver)
```

to:

```python
graph = build_exploration_graph(gemini, driver)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
cd backend && git add src/explorator/api/routes/rounds.py
git commit -m "refactor(m3-prep): rounds.py uses build_exploration_graph"
```

---

### Task 9: Update API Route — realization_rounds.py

**Files:**
- Modify: `backend/src/explorator/api/routes/realization_rounds.py`

- [ ] **Step 1: Update import**

In `backend/src/explorator/api/routes/realization_rounds.py`, change:

```python
from explorator.engine.realization_graph import build_realization_graph
```

to:

```python
from explorator.engine.graph import build_realization_subgraph
```

- [ ] **Step 2: Update graph call**

In the `trigger_realization` function, change:

```python
graph = build_realization_graph(gemini, driver)
```

to:

```python
graph = build_realization_subgraph(gemini, driver)
```

**Important**: The realization endpoint only needs the M2 portion of the pipeline (load_context → ... → persist_realization). The unified graph starts at parse_intent, which requires a `prompt` field. The realization endpoint does NOT have a prompt — it has `progression_candidate_ids`.

**Solution**: Keep a lightweight `build_realization_subgraph()` function in `graph.py` that builds only the M2 portion using the same `ExplorationState` type. This avoids running M1 nodes when only realization is needed:

```python
def build_realization_subgraph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build M2-only subgraph for independent realization."""
    graph = StateGraph(ExplorationState)
    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))
    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", END)
    return graph.compile(recursion_limit=100)
```

Add this to `graph.py` alongside `build_exploration_graph`. The realization endpoint uses `build_realization_subgraph` instead.

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: PASS — or if realization-only flow breaks, revert step 2 and keep `build_realization_graph` import temporarily.

- [ ] **Step 4: Commit**

```bash
cd backend && git add src/explorator/api/routes/realization_rounds.py
git commit -m "refactor(m3-prep): realization_rounds.py uses build_exploration_graph"
```

---

### Task 10: Update Integration Test Imports

**Files:**
- Modify: `backend/tests/integration/test_realization_flow.py`

- [ ] **Step 1: Update imports**

In `backend/tests/integration/test_realization_flow.py`, change all occurrences of:

```python
from explorator.engine.realization_graph import build_realization_graph
```

to:

```python
from explorator.engine.graph import build_realization_subgraph
```

And update any calls from `build_realization_graph(...)` to `build_realization_subgraph(...)`.

The expected node sets in assertions should stay the same — the realization subgraph has the same M2 nodes as before. Just verify the import path changed.

- [ ] **Step 2: Run integration tests**

Run: `cd backend && uv run pytest tests/integration/test_realization_flow.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
cd backend && git add tests/integration/test_realization_flow.py
git commit -m "test(m3-prep): update realization flow tests for unified graph"
```

---

### Task 11: Remove Deprecated Files

**Files:**
- Delete: `backend/src/explorator/engine/realization_graph.py`
- Delete: `backend/src/explorator/engine/realization_state.py`
- Modify: `backend/src/explorator/engine/graph.py` (remove alias)

- [ ] **Step 1: Verify no remaining imports of deleted modules**

Run: `cd backend && grep -r "from explorator.engine.realization_graph" src/ tests/ --include="*.py" -l`
Expected: No files (all updated to `from explorator.engine.graph import build_realization_subgraph`)

Run: `cd backend && grep -r "from explorator.engine.realization_state" src/ tests/ --include="*.py" -l`
Expected: No files (all updated to `from explorator.engine.state import ExplorationState`)

If any files still import these, update them first.

- [ ] **Step 2: Delete deprecated files**

```bash
rm backend/src/explorator/engine/realization_graph.py
rm backend/src/explorator/engine/realization_state.py
```

- [ ] **Step 3: Remove build_m1_graph alias**

In `backend/src/explorator/engine/graph.py`, remove the line:

```python
# Backwards-compatible alias — will be removed after M3-prep completes
build_m1_graph = build_exploration_graph
```

- [ ] **Step 4: Verify no remaining imports of build_m1_graph**

Run: `cd backend && grep -r "build_m1_graph" src/ tests/ --include="*.py" -l`
Expected: No files

- [ ] **Step 5: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 6: Run mypy**

Run: `cd backend && uv run mypy src/explorator/engine/ --strict`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 7: Commit**

```bash
cd backend && git add -A src/explorator/engine/ tests/
git commit -m "refactor(m3-prep): remove RealizationState, realization_graph, build_m1_graph alias"
```

---

### Task 12: Final Verification — Full Suite + Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v --timeout=30`
Expected: All 245+ tests PASS with zero failures

- [ ] **Step 2: Run mypy on full backend**

Run: `cd backend && uv run mypy src/ --strict`
Expected: Clean (or only pre-existing warnings)

- [ ] **Step 3: Run ruff**

Run: `cd backend && uv run ruff check src/ tests/`
Expected: Clean

- [ ] **Step 4: Verify graph compiles with real dependencies (optional — requires Neo4j + Gemini key)**

```bash
cd backend && uv run python -c "
from explorator.engine.graph import build_exploration_graph
from unittest.mock import MagicMock
g = build_exploration_graph(MagicMock(), MagicMock())
print(f'Nodes: {sorted(g.nodes.keys())}')
print('Graph compiled successfully')
"
```

Expected: Lists all 13 nodes + `__start__` + `__end__`, prints success message.

- [ ] **Step 5: Commit (if any fixes were needed)**

```bash
git add -A && git commit -m "fix(m3-prep): final verification fixes"
```
