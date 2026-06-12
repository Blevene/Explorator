# M4b — Explanation, Comparison & Provenance Implementation Plan


**Goal:** On-demand AI explanation of arrangement candidates, side-by-side comparison view with stacked piano rolls and score overlays, live provenance capture during graph execution, and a session history timeline panel.

**Architecture:** Gemini Pro generates structured explanations cached in Neo4j. Provenance events are appended to ExplorationState during graph execution and persisted as a single ProvenanceTrace node per session. Comparison view is frontend-only (reads existing stores) with a fire-and-forget POST for provenance. Session history fetches the ProvenanceTrace and renders a collapsible timeline.

**Tech Stack:** Python (FastAPI, Pydantic, LangGraph), Neo4j, React/Zustand, TypeScript

**Spec:** `docs/design/specs/2026-04-11-m4-export-explanation-design.md` (v1.2, Sections 3.1-3.5, 4.2-4.3)

---

### Task 1: ProvenanceEvent model + ProvenanceTrace repo

**Files:**
- Modify: `backend/src/explorator/models/export.py`
- Create: `backend/src/explorator/graph/provenance_trace_repo.py`
- Create: `backend/tests/unit/models/test_provenance.py`

- [ ] **Step 1: Write failing tests for ProvenanceEvent model**

Create `backend/tests/unit/models/test_provenance.py`:

```python
"""Tests for ProvenanceEvent and ProvenanceTrace models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from explorator.models.export import ProvenanceEvent, ProvenanceTrace


class TestProvenanceEvent:
    """Validate ProvenanceEvent structured creation."""

    def test_minimal_event(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="generate",
            object_id="pc_abc123",
        )
        assert ev.action == "generate"
        assert ev.round_number is None
        assert ev.details == {}

    def test_full_event(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="mutate",
            object_id="pc_abc123",
            round_number=2,
            details={"mutation_type": "substitute_chord", "source_id": "pc_xyz"},
        )
        assert ev.round_number == 2
        assert ev.details["mutation_type"] == "substitute_chord"

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            ProvenanceEvent(action="generate")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self):
        ev = ProvenanceEvent(
            timestamp=datetime(2026, 4, 12, tzinfo=timezone.utc),
            action="rank_and_select",
            object_id="session_123",
            round_number=1,
            details={"roles": {"a": "best"}},
        )
        data = ev.model_dump(mode="json")
        restored = ProvenanceEvent.model_validate(data)
        assert restored.action == ev.action
        assert restored.details == ev.details


class TestProvenanceTraceModel:
    """Validate ProvenanceTrace has session_id and events list."""

    def test_empty_trace(self):
        trace = ProvenanceTrace(
            id="pt_test",
            type="provenance_trace",
            status="active",
            session_id="sess_abc",
        )
        assert trace.events == []
        assert trace.session_id == "sess_abc"

    def test_trace_with_events(self):
        trace = ProvenanceTrace(
            id="pt_test",
            type="provenance_trace",
            status="active",
            session_id="sess_abc",
            events=[
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        )
        assert len(trace.events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/models/test_provenance.py -v`
Expected: FAIL with `ImportError` (ProvenanceEvent not yet in models/export.py).

- [ ] **Step 3: Add ProvenanceEvent to models/export.py**

In `backend/src/explorator/models/export.py`, add after the existing imports:

```python
from datetime import datetime


class ProvenanceEvent(BaseModel):
    """Single event in a provenance timeline."""

    timestamp: datetime
    action: str
    object_id: str
    round_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
```

Place this class **before** the existing `ProvenanceTrace` class.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/models/test_provenance.py -v`
Expected: All 6 tests pass.

- [ ] **Step 5: Write failing tests for ProvenanceTraceRepo**

Append to `backend/tests/unit/models/test_provenance.py`:

```python
import pytest_asyncio
from neo4j import AsyncDriver

from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo
from explorator.models.export import ProvenanceTrace
from explorator.utils import utc_now


class TestProvenanceTraceRepo:
    """Integration tests for ProvenanceTraceRepo (requires Neo4j)."""

    @pytest_asyncio.fixture
    async def repo(self, neo4j_driver: AsyncDriver) -> ProvenanceTraceRepo:
        return ProvenanceTraceRepo(neo4j_driver)

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test1",
            type="provenance_trace",
            status="active",
            session_id="sess_test1",
            events=[],
        )
        await repo.create(trace)
        result = await repo.get_by_id("pt_test1")
        assert result is not None
        assert result["session_id"] == "sess_test1"

    @pytest.mark.asyncio
    async def test_append_events(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test2",
            type="provenance_trace",
            status="active",
            session_id="sess_test2",
            events=[
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        )
        await repo.create(trace)

        new_events = [
            {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2"},
            {"timestamp": "2026-04-12T00:02:00Z", "action": "rank_and_select", "object_id": "sess_test2"},
        ]
        await repo.append_events("pt_test2", new_events)

        result = await repo.get_by_id("pt_test2")
        assert result is not None
        assert len(result["events"]) == 3
        assert result["events"][0]["action"] == "generate"
        assert result["events"][2]["action"] == "rank_and_select"

    @pytest.mark.asyncio
    async def test_append_events_not_found(self, repo: ProvenanceTraceRepo):
        """append_events on nonexistent trace should raise."""
        with pytest.raises(ValueError, match="not found"):
            await repo.append_events("pt_nonexistent", [{"action": "test"}])

    @pytest.mark.asyncio
    async def test_get_by_session_id(self, repo: ProvenanceTraceRepo):
        trace = ProvenanceTrace(
            id="pt_test3",
            type="provenance_trace",
            status="active",
            session_id="sess_test3",
            events=[],
        )
        await repo.create(trace)
        result = await repo.get_by_session_id("sess_test3")
        assert result is not None
        assert result["id"] == "pt_test3"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/models/test_provenance.py::TestProvenanceTraceRepo -v`
Expected: FAIL with `ImportError` (ProvenanceTraceRepo does not exist yet).

- [ ] **Step 7: Implement ProvenanceTraceRepo**

Create `backend/src/explorator/graph/provenance_trace_repo.py`:

```python
"""Neo4j repository for ProvenanceTrace entities."""

import json
from typing import Any

from explorator.graph.repository import BaseRepository, _neo4j_deserialize
from explorator.utils import utc_now


class ProvenanceTraceRepo(BaseRepository):
    """CRUD + append_events for ProvenanceTrace nodes."""

    label = "ProvenanceTrace"

    async def append_events(
        self, trace_id: str, new_events: list[dict[str, Any]]
    ) -> None:
        """Append new provenance events to an existing trace.

        Loads the current events list, extends it, and writes back.
        Raises ValueError if the trace does not exist.
        """
        existing = await self.get_by_id(trace_id)
        if existing is None:
            raise ValueError(f"ProvenanceTrace {trace_id} not found")

        current_events: list[dict[str, Any]] = existing.get("events", [])
        merged = current_events + new_events
        events_json = json.dumps(merged)

        query = f"""
            MATCH (n:{self.label} {{id: $id}})
            SET n.events = $events, n.updated_at = $now
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                id=trace_id,
                events=events_json,
                now=utc_now().isoformat(),
            )

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        """Fetch the provenance trace for a given session."""
        results = await self.query_by_property("session_id", session_id)
        return results[0] if results else None
```

- [ ] **Step 8: Run all provenance tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/models/test_provenance.py -v`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/src/explorator/models/export.py backend/src/explorator/graph/provenance_trace_repo.py backend/tests/unit/models/test_provenance.py
git commit -m "feat(m4b): add ProvenanceEvent model and ProvenanceTraceRepo with append_events"
```

---

### Task 2: ExplorationState + provenance init in graph.py

**Files:**
- Modify: `backend/src/explorator/engine/state.py`
- Modify: `backend/src/explorator/engine/graph.py`
- Create: `backend/tests/unit/engine/test_provenance_init.py`

- [ ] **Step 1: Write failing test for provenance_events field on ExplorationState**

Create `backend/tests/unit/engine/test_provenance_init.py`:

```python
"""Tests for provenance_events initialization in the exploration graph."""

from explorator.engine.state import ExplorationState


class TestProvenanceStateField:
    """Verify provenance_events is a valid field on ExplorationState."""

    def test_state_accepts_provenance_events(self):
        state: ExplorationState = {
            "session_id": "sess_test",
            "provenance_events": [],
        }
        assert state["provenance_events"] == []

    def test_state_provenance_events_with_data(self):
        state: ExplorationState = {
            "session_id": "sess_test",
            "provenance_events": [
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
            ],
        }
        assert len(state["provenance_events"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_init.py -v`
Expected: FAIL with TypedDict key error (field not yet defined).

- [ ] **Step 3: Add provenance_events to ExplorationState**

In `backend/src/explorator/engine/state.py`, add after the `feedback_history` / `user_preference_profile` block (before the `# Progress callback` section):

```python
    # --- M4b: Provenance ---
    provenance_events: list[dict[str, Any]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_init.py -v`
Expected: Both tests pass.

- [ ] **Step 5: Write test verifying graph initialization sets provenance_events**

Append to `backend/tests/unit/engine/test_provenance_init.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.engine.graph import build_exploration_graph


class TestGraphProvenanceInit:
    """Verify build_exploration_graph produces a compiled graph
    that would receive provenance_events in initial state."""

    def test_graph_compiles_without_error(self):
        """Smoke test: the graph compiles with mock dependencies."""
        gemini = MagicMock()
        driver = MagicMock()
        graph = build_exploration_graph(gemini, driver)
        assert graph is not None
```

- [ ] **Step 6: Initialize provenance_events in graph.py**

In `backend/src/explorator/engine/graph.py`, modify `build_exploration_graph` to return a wrapper that injects `provenance_events: []` into the initial state. Add a thin wrapper function below the existing `build_exploration_graph`:

```python
def build_exploration_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the unified M1+M2 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # M1 nodes
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)

    # M3b: memory/feedback node
    graph.add_node("load_memory", partial(load_memory, driver=driver))

    # M2 nodes (shared registration)
    _add_m2_nodes(graph, gemini, driver)

    # Persistence
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Linear flow: M1 -> M2 -> persist
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "load_memory")
    graph.add_edge("load_memory", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "load_context")
    _add_m2_edges(graph)

    # M3a: mutation loop
    graph.add_node("check_stop", check_stop)
    graph.add_node("mutate", partial(mutate, gemini=gemini))

    graph.add_edge("rank_and_select", "check_stop")

    # Conditional: stop -> persist, continue -> mutate
    graph.add_conditional_edges("check_stop", _route_after_stop, {
        "persist_realization": "persist_realization",
        "mutate": "mutate",
    })

    # Conditional: harmonic -> evaluate_progressions, arrangement -> evaluate_arrangements
    graph.add_conditional_edges("mutate", _route_after_mutate, {
        "evaluate_progressions": "evaluate_progressions",
        "evaluate_arrangements": "evaluate_arrangements",
    })

    graph.add_edge("persist_realization", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()
```

The initialization of `provenance_events` happens at the **call site** where the graph is invoked. The graph's entry state must include `"provenance_events": []`. Find the call site in the rounds route.

In `backend/src/explorator/api/routes/rounds.py`, locate where the graph is invoked (the `ainvoke` call) and ensure `provenance_events` is included in the initial state dict:

```python
# Add to the initial state dict passed to graph.ainvoke()
"provenance_events": [],
```

- [ ] **Step 7: Find and update the graph invocation call site**

Read `backend/src/explorator/api/routes/rounds.py` to find the graph invocation and add `"provenance_events": []` to the initial state.

- [ ] **Step 8: Run full test to verify**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_init.py -v`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/src/explorator/engine/state.py backend/src/explorator/engine/graph.py backend/src/explorator/api/routes/rounds.py backend/tests/unit/engine/test_provenance_init.py
git commit -m "feat(m4b): add provenance_events to ExplorationState, init in graph invocation"
```

---

### Task 3: Instrument graph nodes with provenance event appends

**Files:**
- Modify: `backend/src/explorator/engine/nodes/generate.py`
- Modify: `backend/src/explorator/engine/nodes/mutate.py`
- Modify: `backend/src/explorator/engine/nodes/load_memory.py`
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Create: `backend/tests/unit/engine/test_provenance_instrumentation.py`

- [ ] **Step 1: Write failing tests for provenance instrumentation**

Create `backend/tests/unit/engine/test_provenance_instrumentation.py`:

```python
"""Tests for provenance event instrumentation in graph nodes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.engine.state import ExplorationState


def _make_state(**overrides) -> ExplorationState:
    """Build a minimal ExplorationState with provenance_events initialized."""
    base: ExplorationState = {
        "session_id": "sess_test",
        "prompt": "dreamy chords",
        "genre": "dream_pop",
        "provenance_events": [],
        "round_number": 1,
        "n_candidates": 6,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestGenerateProvenance:
    """generate node should append a provenance event."""

    @pytest.mark.asyncio
    async def test_generate_appends_provenance_event(self):
        from explorator.engine.nodes.generate import generate

        mock_gemini = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.model_dump.return_value = {
            "id": "pc_1",
            "chord_symbols": ["C", "Am"],
        }

        with patch(
            "explorator.engine.nodes.generate.HarmonyGenerator"
        ) as MockGen:
            instance = MockGen.return_value
            instance.generate = AsyncMock(return_value=[mock_candidate, mock_candidate])

            state = _make_state(
                creative_brief={"key_center": "C", "mode": "major", "phrase_length_bars": 4},
                genre_profile={},
            )
            result = await generate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "generate"
        assert events[0]["details"]["candidate_count"] == 2
        assert "timestamp" in events[0]

    @pytest.mark.asyncio
    async def test_generate_preserves_existing_events(self):
        from explorator.engine.nodes.generate import generate

        mock_gemini = MagicMock()
        mock_candidate = MagicMock()
        mock_candidate.model_dump.return_value = {"id": "pc_1", "chord_symbols": ["C"]}

        with patch(
            "explorator.engine.nodes.generate.HarmonyGenerator"
        ) as MockGen:
            instance = MockGen.return_value
            instance.generate = AsyncMock(return_value=[mock_candidate])

            existing_event = {"timestamp": "prior", "action": "test", "object_id": "x"}
            state = _make_state(
                creative_brief={"key_center": "C", "mode": "major", "phrase_length_bars": 4},
                genre_profile={},
                provenance_events=[existing_event],
            )
            result = await generate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) == 2
        assert events[0]["action"] == "test"
        assert events[1]["action"] == "generate"


class TestMutateProvenance:
    """mutate node should append a provenance event per mutation."""

    @pytest.mark.asyncio
    async def test_mutate_appends_provenance_events(self):
        from explorator.engine.nodes.mutate import mutate

        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.mutated_chord_symbols = ["Dm7", "G7", "Cmaj7", "Am7"]
        mock_mutation = MagicMock()
        mock_mutation.operation = "substitute_chord"
        mock_mutation.position = 0
        mock_mutation.original_value = "C"
        mock_mutation.new_value = "Dm7"
        mock_mutation.description = "sub chord"
        mock_mutation.reason = "improve tension"
        mock_mutation.predicted_score_changes = []
        mock_response.mutations = [mock_mutation]

        with patch(
            "explorator.engine.nodes.mutate.HarmonyMutator"
        ) as MockMut:
            instance = MockMut.return_value
            instance.mutate_harmonic = AsyncMock(return_value=mock_response)

            state = _make_state(
                progression_candidates=[
                    {"id": "pc_1", "chord_symbols": ["C", "Am", "F", "G"], "metadata": {"scores": {"genre_fit": 7.0}}},
                ],
                scorecards=[
                    {"candidate_id": "arr_1", "weighted_total": 7.5, "scores": {"genre_fit": 7.0}},
                ],
                arrangement_candidates=[
                    {"id": "arr_1", "progression_candidate_id": "pc_1"},
                ],
                search_plan={"mutation_budget_per_round": 2},
                pareto_front={"candidate_ids": ["arr_1"]},
                mutation_records=[],
                all_candidates_history=[],
                genre_profile={"genre": "dream_pop"},
            )
            result = await mutate(state, gemini=mock_gemini)

        events = result.get("provenance_events", [])
        assert len(events) >= 1
        mutate_events = [e for e in events if e["action"] == "mutate"]
        assert len(mutate_events) == 1
        assert "source_candidate_id" in mutate_events[0]["details"]


class TestRankAndSelectProvenance:
    """rank_and_select should append a provenance event."""

    @pytest.mark.asyncio
    async def test_rank_and_select_appends_provenance_event(self):
        from explorator.engine.nodes.rank_and_select import rank_and_select

        state = _make_state(
            arrangement_candidates=[
                {
                    "id": "arr_1",
                    "progression_candidate_id": "pc_1",
                    "status": "pending",
                },
            ],
            arrangement_families=[],
            progression_candidates=[
                {"id": "pc_1", "chord_symbols": ["C", "Am", "F", "G"], "metadata": {"scores": {"genre_fit": 7.0}}},
            ],
            evaluations=[
                {
                    "arrangement_candidate_id": "arr_1",
                    "voice_leading": {"overall_score": 8.0},
                    "register_density": {"overall_score": 7.5},
                    "playability": {"overall_score": 8.5},
                },
            ],
            search_plan={"diversity_target": 0.65},
        )
        result = await rank_and_select(state)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "rank_and_select"
        assert "role_assignments" in events[0]["details"]


class TestLoadMemoryProvenance:
    """load_memory should append a provenance event when feedback is loaded."""

    @pytest.mark.asyncio
    async def test_load_memory_appends_event_with_feedback(self):
        from explorator.engine.nodes.load_memory import load_memory

        mock_driver = MagicMock()

        with patch(
            "explorator.engine.nodes.load_memory.FeedbackEventRepo"
        ) as MockFB, patch(
            "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
        ) as MockOW:
            fb_instance = MockFB.return_value
            fb_instance.list_by_session = AsyncMock(return_value=[
                {"id": "fb_1", "text": "more tension", "weight_deltas": {"tension_curve": 0.5}},
            ])

            ow_instance = MockOW.return_value
            ow_instance.get_latest_for_session = AsyncMock(return_value=None)

            state = _make_state()
            result = await load_memory(state, driver=mock_driver)

        events = result.get("provenance_events", [])
        assert len(events) == 1
        assert events[0]["action"] == "feedback"
        assert events[0]["details"]["feedback_count"] == 1

    @pytest.mark.asyncio
    async def test_load_memory_no_event_without_feedback(self):
        from explorator.engine.nodes.load_memory import load_memory

        mock_driver = MagicMock()

        with patch(
            "explorator.engine.nodes.load_memory.FeedbackEventRepo"
        ) as MockFB, patch(
            "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
        ) as MockOW:
            fb_instance = MockFB.return_value
            fb_instance.list_by_session = AsyncMock(return_value=[])

            ow_instance = MockOW.return_value
            ow_instance.get_latest_for_session = AsyncMock(return_value=None)

            state = _make_state()
            result = await load_memory(state, driver=mock_driver)

        events = result.get("provenance_events", [])
        assert len(events) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_instrumentation.py -v`
Expected: FAIL (nodes don't yet return provenance_events).

- [ ] **Step 3: Instrument generate node**

In `backend/src/explorator/engine/nodes/generate.py`, add at the top:

```python
from explorator.utils import utc_now
```

Then, before the `return` statement at the end of the `generate` function, add:

```python
    # M4b: Provenance event
    existing_events = list(state.get("provenance_events", []))
    existing_events.append({
        "timestamp": utc_now().isoformat(),
        "action": "generate",
        "object_id": state["session_id"],
        "round_number": state.get("round_number", 1),
        "details": {
            "candidate_count": len(serialized),
            "prompt_summary": state.get("prompt", "")[:100],
        },
    })
```

And update the return dict to include:

```python
    return {"progression_candidates": serialized, "provenance_events": existing_events}
```

- [ ] **Step 4: Instrument mutate node**

In `backend/src/explorator/engine/nodes/mutate.py`, after the `for source_id in to_mutate:` loop completes (after building `new_records`), add before the `history_snapshot` line:

```python
    # M4b: Provenance events
    existing_events = list(state.get("provenance_events", []))
    now_iso = now.isoformat()
    for rec in new_records:
        existing_events.append({
            "timestamp": now_iso,
            "action": "mutate",
            "object_id": rec["result_candidate_id"],
            "round_number": round_number + 1,
            "details": {
                "source_candidate_id": rec["source_candidate_id"],
                "mutation_type": rec["changes"][0]["operation"] if rec.get("changes") else "unknown",
                "result_candidate_id": rec["result_candidate_id"],
            },
        })
```

And update the return dict to include `"provenance_events": existing_events`.

The full return statement becomes:

```python
    return {
        "progression_candidates": existing_progs + new_progs,
        "mutation_records": existing_records + new_records,
        "all_candidates_history": existing_history + history_snapshot,
        "round_number": round_number + 1,
        "last_mutation_scope": "harmonic",
        "voicing_plans": [],
        "bass_lines": [],
        "arrangement_candidates": [],
        "arrangement_families": [],
        "selected_arrangements": [],
        "evaluations": [],
        "scorecards": [],
        "provenance_events": existing_events,
    }
```

- [ ] **Step 5: Instrument load_memory node**

In `backend/src/explorator/engine/nodes/load_memory.py`, add at the top:

```python
from explorator.utils import utc_now
```

Then, before the return statement, add:

```python
    # M4b: Provenance event — only log when feedback was actually loaded
    existing_events = list(state.get("provenance_events", []))
    if feedback_history:
        existing_events.append({
            "timestamp": utc_now().isoformat(),
            "action": "feedback",
            "object_id": session_id,
            "round_number": None,
            "details": {
                "feedback_count": len(feedback_history),
                "weight_deltas": {
                    fb.get("id", ""): fb.get("weight_deltas", {})
                    for fb in feedback_history
                    if fb.get("weight_deltas")
                },
            },
        })
```

And update the return dict to include `"provenance_events": existing_events`.

The full return statement becomes:

```python
    return {
        "feedback_history": feedback_history,
        "objective_weights": objective_weights,
        "user_preference_profile": user_preference_profile,
        "provenance_events": existing_events,
    }
```

- [ ] **Step 6: Instrument rank_and_select node**

In `backend/src/explorator/engine/nodes/rank_and_select.py`, add at the top if not already present:

```python
from explorator.utils import utc_now
```

(Note: `utc_now` is already imported.)

Before the return statement, add:

```python
    # M4b: Provenance event
    existing_events = list(state.get("provenance_events", []))
    existing_events.append({
        "timestamp": utc_now().isoformat(),
        "action": "rank_and_select",
        "object_id": state.get("session_id", ""),
        "round_number": state.get("round_number", 1),
        "details": {
            "role_assignments": selection_roles,
            "selected_count": len(selected_arrangements),
            "pareto_count": len(pareto_ids),
        },
    })
```

And update the return dict to include `"provenance_events": existing_events`.

The full return statement becomes:

```python
    return {
        "arrangement_candidates": updated_arrangements,
        "scorecards": scorecards,
        "selected_arrangements": selected_arrangements,
        "arrangement_families": updated_families,
        "pareto_front": pareto_snapshot,
        "final_selection": final_selection,
        "provenance_events": existing_events,
    }
```

- [ ] **Step 7: Run all provenance instrumentation tests**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_instrumentation.py -v`
Expected: All tests pass.

- [ ] **Step 8: Run existing node tests to verify no regressions**

Run: `cd backend && uv run python -m pytest tests/unit/engine/ -v`
Expected: All existing tests pass (new return keys are additive — callers ignore unknown keys).

- [ ] **Step 9: Commit**

```bash
git add backend/src/explorator/engine/nodes/generate.py backend/src/explorator/engine/nodes/mutate.py backend/src/explorator/engine/nodes/load_memory.py backend/src/explorator/engine/nodes/rank_and_select.py backend/tests/unit/engine/test_provenance_instrumentation.py
git commit -m "feat(m4b): instrument generate, mutate, load_memory, rank_and_select with provenance events"
```

---

### Task 4: Persist provenance in persist_round

**Files:**
- Modify: `backend/src/explorator/engine/nodes/persist_round.py`
- Create: `backend/tests/unit/engine/test_persist_provenance.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/engine/test_persist_provenance.py`:

```python
"""Tests for provenance persistence in persist_round node."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.engine.state import ExplorationState


def _make_state(**overrides) -> ExplorationState:
    base: ExplorationState = {
        "session_id": "sess_test",
        "prompt": "test",
        "genre": "dream_pop",
        "round_number": 1,
        "provenance_events": [],
        "top_progressions": [],
        "scorecards": [],
        "mutation_records": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestPersistRoundProvenance:
    """persist_round should write accumulated provenance events to ProvenanceTrace."""

    @pytest.mark.asyncio
    async def test_persist_round_creates_trace_on_first_run(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        events = [
            {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1"},
        ]

        with patch(
            "explorator.engine.nodes.persist_round.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.ProgressionCandidateRepo"
        ), patch(
            "explorator.engine.nodes.persist_round.SearchRoundRepo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.MutationRecordRepo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock(return_value=None)
            repo_instance.create = AsyncMock()
            repo_instance.append_events = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=events)
            await persist_round(state, driver=mock_driver)

            # Should create a new trace (not append)
            repo_instance.create.assert_called_once()
            created_trace = repo_instance.create.call_args[0][0]
            assert created_trace.session_id == "sess_test"
            assert len(created_trace.events) == 1

    @pytest.mark.asyncio
    async def test_persist_round_appends_to_existing_trace(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        events = [
            {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2"},
        ]

        with patch(
            "explorator.engine.nodes.persist_round.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.ProgressionCandidateRepo"
        ), patch(
            "explorator.engine.nodes.persist_round.SearchRoundRepo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.MutationRecordRepo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock(return_value={
                "id": "pt_existing",
                "session_id": "sess_test",
                "events": [{"action": "generate"}],
            })
            repo_instance.append_events = AsyncMock()
            repo_instance.create = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=events)
            await persist_round(state, driver=mock_driver)

            # Should append, not create
            repo_instance.append_events.assert_called_once_with("pt_existing", events)
            repo_instance.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_round_no_events_skips_provenance(self):
        from explorator.engine.nodes.persist_round import persist_round

        mock_driver = MagicMock()
        mock_neo_session = AsyncMock()
        mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
        mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "explorator.engine.nodes.persist_round.ProvenanceTraceRepo"
        ) as MockRepo, patch(
            "explorator.engine.nodes.persist_round.ProgressionCandidateRepo"
        ), patch(
            "explorator.engine.nodes.persist_round.SearchRoundRepo"
        ) as MockSR, patch(
            "explorator.engine.nodes.persist_round.MutationRecordRepo"
        ) as MockMR:
            repo_instance = MockRepo.return_value
            repo_instance.get_by_session_id = AsyncMock()
            repo_instance.create = AsyncMock()
            repo_instance.append_events = AsyncMock()

            MockSR.return_value.create = AsyncMock()
            MockMR.return_value.create = AsyncMock()

            state = _make_state(provenance_events=[])
            await persist_round(state, driver=mock_driver)

            # No provenance events — skip entirely
            repo_instance.get_by_session_id.assert_not_called()
            repo_instance.create.assert_not_called()
            repo_instance.append_events.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_persist_provenance.py -v`
Expected: FAIL (ProvenanceTraceRepo not imported in persist_round.py).

- [ ] **Step 3: Add provenance persistence to persist_round.py**

In `backend/src/explorator/engine/nodes/persist_round.py`, add import:

```python
from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo
from explorator.models.export import ProvenanceTrace
```

Then, at the end of the `persist_round` function, before the final callback block, add:

```python
    # --- M4b: Persist provenance events ---
    provenance_events = state.get("provenance_events", [])
    if provenance_events:
        try:
            prov_repo = ProvenanceTraceRepo(driver)
            existing_trace = await prov_repo.get_by_session_id(session_id)
            if existing_trace:
                await prov_repo.append_events(existing_trace["id"], provenance_events)
            else:
                new_trace = ProvenanceTrace(
                    id=f"pt_{ULID()}",
                    type="provenance_trace",
                    status="active",
                    session_id=session_id,
                    events=provenance_events,
                )
                await prov_repo.create(new_trace)
        except Exception:
            logger.exception("Failed to persist provenance events")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_persist_provenance.py -v`
Expected: All 3 tests pass.

- [ ] **Step 5: Run existing persist_round tests**

Run: `cd backend && uv run python -m pytest tests/unit/engine/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/nodes/persist_round.py backend/tests/unit/engine/test_persist_provenance.py
git commit -m "feat(m4b): persist provenance events to ProvenanceTrace in persist_round"
```

---

### Task 5: Explanation prompt

**Files:**
- Create: `backend/src/explorator/prompts/explanation.py`
- Create: `backend/tests/unit/prompts/test_explanation_prompt.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/prompts/test_explanation_prompt.py`:

```python
"""Tests for explanation prompt generation."""

import pytest

from explorator.prompts.explanation import explanation_prompt


class TestExplanationPrompt:
    """Verify explanation_prompt returns (user_prompt, system_prompt) tuple."""

    def test_returns_tuple(self):
        result = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=["Use extended chords", "Avoid power chords"],
            scores={"voice_leading": 8.5, "tension_curve": 7.2, "playability": 9.0},
            mutation_lineage=None,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_user_prompt_contains_chords(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
            key_center="C",
            mode="major",
            genre="synthwave",
            genre_rules=[],
            scores={"voice_leading": 8.0},
            mutation_lineage=None,
        )
        assert "Cmaj7" in user_prompt
        assert "synthwave" in user_prompt
        assert "voice_leading" in user_prompt

    def test_user_prompt_contains_roman_numerals(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7"],
            roman_numerals=["Imaj7", "vim7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert "Imaj7" in user_prompt

    def test_user_prompt_includes_mutation_lineage(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Dm7", "G7", "Cmaj7", "Am7"],
            roman_numerals=["iim7", "V7", "Imaj7", "vim7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={"voice_leading": 7.0},
            mutation_lineage=["reharmonize bar 3", "smooth voice leading"],
        )
        assert "reharmonize bar 3" in user_prompt
        assert "smooth voice leading" in user_prompt

    def test_user_prompt_omits_lineage_when_none(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["C", "Am"],
            roman_numerals=["I", "vi"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert "mutation" not in user_prompt.lower() or "lineage" not in user_prompt.lower()

    def test_system_prompt_is_nonempty(self):
        _, system_prompt = explanation_prompt(
            chord_symbols=["C"],
            roman_numerals=["I"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert len(system_prompt) > 20

    def test_genre_rules_included(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["C"],
            roman_numerals=["I"],
            key_center="C",
            mode="major",
            genre="synthwave",
            genre_rules=["Use seventh chords", "Prefer minor keys"],
            scores={},
            mutation_lineage=None,
        )
        assert "Use seventh chords" in user_prompt
        assert "Prefer minor keys" in user_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/prompts/test_explanation_prompt.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement explanation_prompt**

Create `backend/src/explorator/prompts/explanation.py`:

```python
"""Explanation prompts for candidate analysis."""

from __future__ import annotations


def explanation_prompt(
    chord_symbols: list[str],
    roman_numerals: list[str],
    key_center: str,
    mode: str,
    genre: str,
    genre_rules: list[str],
    scores: dict[str, float],
    mutation_lineage: list[str] | None = None,
) -> tuple[str, str]:
    """Build (user_prompt, system_prompt) for candidate explanation.

    Returns a tuple of (user_prompt, system_prompt) strings suitable for
    passing to GeminiClient.generate_structured.
    """
    scores_str = ", ".join(f"{k}={v:.1f}" for k, v in scores.items()) if scores else "none"
    rules_str = "; ".join(genre_rules) if genre_rules else "none specified"

    user_lines = [
        f"Chord progression: {' | '.join(chord_symbols)}",
        f"Roman numeral analysis: {' | '.join(roman_numerals)}",
        f"Key: {key_center} {mode}",
        f"Genre: {genre}",
        f"Genre rules: {rules_str}",
        f"Evaluation scores: {scores_str}",
    ]

    if mutation_lineage:
        user_lines += [
            "",
            f"Mutation history: {', '.join(mutation_lineage)}",
        ]

    user_lines += [
        "",
        "Analyze this chord progression and provide:",
        "- summary: A single sentence describing the character and feel of this progression",
        "- why_it_works: 2-4 bullet points explaining what makes it effective in this genre",
        "- what_is_experimental: 1-3 bullet points about what is unconventional or risky",
        "- recommended_use_cases: 2-3 suggestions for where to use it (intro, verse, bridge, chorus, etc.)",
    ]

    system_prompt = (
        "You are a music theory expert and creative producer specializing in "
        "chord progression analysis. Your explanations should be insightful, "
        "accessible to intermediate musicians, and grounded in both theory and "
        "practical production context. Be specific about harmonic devices "
        "(modal interchange, secondary dominants, tritone substitutions, etc.) "
        "rather than vague. Reference the genre conventions when relevant."
    )

    return "\n".join(user_lines), system_prompt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/prompts/test_explanation_prompt.py -v`
Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/prompts/explanation.py backend/tests/unit/prompts/test_explanation_prompt.py
git commit -m "feat(m4b): add explanation prompt following centralized prompt pattern"
```

---

### Task 6: CandidateExplanation repo + API route

**Files:**
- Create: `backend/src/explorator/graph/candidate_explanation_repo.py`
- Create: `backend/src/explorator/api/routes/explanations.py`
- Modify: `backend/src/explorator/api/app.py`
- Create: `backend/tests/unit/engine/test_explanation_api.py`

- [ ] **Step 1: Write failing tests for the explanation repo**

Create `backend/tests/unit/engine/test_explanation_api.py`:

```python
"""Tests for CandidateExplanation repo and API route."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.graph.candidate_explanation_repo import CandidateExplanationRepo
from explorator.models.export import CandidateExplanation


class TestCandidateExplanationRepo:
    """Integration tests for CandidateExplanationRepo."""

    @pytest_asyncio.fixture
    async def repo(self, neo4j_driver) -> CandidateExplanationRepo:
        return CandidateExplanationRepo(neo4j_driver)

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo: CandidateExplanationRepo):
        explanation = CandidateExplanation(
            id="ce_test1",
            type="candidate_explanation",
            status="active",
            session_id="sess_test",
            candidate_id="arr_test1",
            summary="A dreamy progression with modal interchange.",
            why_it_works=["Uses borrowed chords for color"],
            what_is_experimental=["Tritone sub in bar 3"],
            recommended_use_cases=["Intro section", "Bridge"],
        )
        await repo.create(explanation)
        result = await repo.get_by_id("ce_test1")
        assert result is not None
        assert result["summary"] == "A dreamy progression with modal interchange."

    @pytest.mark.asyncio
    async def test_get_by_candidate_id(self, repo: CandidateExplanationRepo):
        explanation = CandidateExplanation(
            id="ce_test2",
            type="candidate_explanation",
            status="active",
            session_id="sess_test",
            candidate_id="arr_test2",
            summary="Smooth voice leading.",
        )
        await repo.create(explanation)
        result = await repo.get_by_candidate_id("arr_test2")
        assert result is not None
        assert result["id"] == "ce_test2"

    @pytest.mark.asyncio
    async def test_get_by_candidate_id_not_found(self, repo: CandidateExplanationRepo):
        result = await repo.get_by_candidate_id("nonexistent")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_explanation_api.py::TestCandidateExplanationRepo -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement CandidateExplanationRepo**

Create `backend/src/explorator/graph/candidate_explanation_repo.py`:

```python
"""Neo4j repository for CandidateExplanation entities."""

from typing import Any

from explorator.graph.repository import BaseRepository


class CandidateExplanationRepo(BaseRepository):
    """CRUD operations for CandidateExplanation nodes."""

    label = "CandidateExplanation"

    async def get_by_candidate_id(self, candidate_id: str) -> dict[str, Any] | None:
        """Fetch a cached explanation for a given candidate."""
        results = await self.query_by_property("candidate_id", candidate_id)
        return results[0] if results else None
```

- [ ] **Step 4: Run repo tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_explanation_api.py::TestCandidateExplanationRepo -v`
Expected: All 3 tests pass.

- [ ] **Step 5: Write failing tests for the explanation API route**

Append to `backend/tests/unit/engine/test_explanation_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.explanations import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestExplanationRoute:
    """Unit tests for explanation endpoints using mocked dependencies."""

    def test_get_cached_explanation_404(self):
        """GET returns 404 when no explanation exists."""
        app = _make_app()

        with patch(
            "explorator.api.routes.explanations.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "explorator.api.routes.explanations.CandidateExplanationRepo"
            ) as MockRepo:
                MockRepo.return_value.get_by_candidate_id = AsyncMock(return_value=None)

                client = TestClient(app)
                resp = client.get("/v1/candidates/arr_x/explanation")
                assert resp.status_code == 404

    def test_get_cached_explanation_200(self):
        """GET returns cached explanation."""
        app = _make_app()

        cached = {
            "id": "ce_1",
            "candidate_id": "arr_x",
            "session_id": "sess_1",
            "summary": "Dreamy",
            "why_it_works": ["Modal interchange"],
            "what_is_experimental": [],
            "recommended_use_cases": ["Intro"],
        }

        with patch(
            "explorator.api.routes.explanations.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            with patch(
                "explorator.api.routes.explanations.CandidateExplanationRepo"
            ) as MockRepo:
                MockRepo.return_value.get_by_candidate_id = AsyncMock(return_value=cached)

                client = TestClient(app)
                resp = client.get("/v1/candidates/arr_x/explanation")
                assert resp.status_code == 200
                data = resp.json()
                assert data["summary"] == "Dreamy"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_explanation_api.py::TestExplanationRoute -v`
Expected: FAIL with `ImportError` (route does not exist).

- [ ] **Step 7: Implement explanation API route**

Create `backend/src/explorator/api/routes/explanations.py`:

```python
"""Explanation API routes — generate and cache candidate explanations."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.graph.candidate_explanation_repo import CandidateExplanationRepo
from explorator.graph.repository import BaseRepository
from explorator.models.export import CandidateExplanation
from explorator.prompts.explanation import explanation_prompt
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)
router = APIRouter(tags=["explanations"])


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class GenreRuleRepo(BaseRepository):
    label = "GenreRule"


class ExplanationResponse(BaseModel):
    """Structured explanation of a candidate."""

    summary: str
    why_it_works: list[str]
    what_is_experimental: list[str]
    recommended_use_cases: list[str]


class GeminiExplanationOutput(BaseModel):
    """Schema for Gemini structured output."""

    summary: str
    why_it_works: list[str]
    what_is_experimental: list[str]
    recommended_use_cases: list[str]


@router.get("/candidates/{candidate_id}/explanation")
async def get_explanation(
    candidate_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> ExplanationResponse:
    """Get a cached explanation for a candidate (404 if not generated)."""
    repo = CandidateExplanationRepo(driver)
    cached = await repo.get_by_candidate_id(candidate_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Explanation not generated yet")
    return ExplanationResponse(
        summary=cached.get("summary", ""),
        why_it_works=cached.get("why_it_works", []),
        what_is_experimental=cached.get("what_is_experimental", []),
        recommended_use_cases=cached.get("recommended_use_cases", []),
    )


@router.post("/candidates/{candidate_id}/explain")
async def generate_or_get_explanation(
    candidate_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
) -> ExplanationResponse:
    """Generate or return cached explanation for a candidate.

    Checks Neo4j cache first. If not found, loads context,
    calls Gemini Pro, persists, and returns.
    """
    explanation_repo = CandidateExplanationRepo(driver)

    # Check cache
    cached = await explanation_repo.get_by_candidate_id(candidate_id)
    if cached is not None:
        return ExplanationResponse(
            summary=cached.get("summary", ""),
            why_it_works=cached.get("why_it_works", []),
            what_is_experimental=cached.get("what_is_experimental", []),
            recommended_use_cases=cached.get("recommended_use_cases", []),
        )

    # Load ArrangementCandidate
    ac_repo = ArrangementCandidateRepo(driver)
    ac_data = await ac_repo.get_by_id(candidate_id)
    if ac_data is None:
        raise HTTPException(status_code=404, detail="ArrangementCandidate not found")

    # Load parent ProgressionCandidate
    prog_id = ac_data.get("progression_candidate_id", "")
    prog_repo = ProgressionCandidateRepo(driver)
    prog_data = await prog_repo.get_by_id(prog_id) if prog_id else None
    if prog_data is None:
        raise HTTPException(
            status_code=422,
            detail=f"ProgressionCandidate not found for arrangement {candidate_id}",
        )

    session_id = ac_data.get("session_id", prog_data.get("session_id", ""))

    # Extract data
    chord_symbols = prog_data.get("chord_symbols", [])
    roman_numerals = prog_data.get("roman_numerals", [])
    key_center = prog_data.get("key_center", "C")
    mode = prog_data.get("mode", "major")
    prog_meta = parse_json_or_dict(prog_data.get("metadata", {}))
    genre = prog_meta.get("genre", prog_data.get("genre", ""))

    # Scores from arrangement metadata/scorecard
    ac_meta = parse_json_or_dict(ac_data.get("metadata", {}))
    scores: dict[str, float] = ac_meta.get("scores", {})
    if not scores:
        scores = prog_meta.get("scores", {})

    # Genre rules
    genre_rules: list[str] = []
    if genre:
        rule_repo = GenreRuleRepo(driver)
        rules_data = await rule_repo.query_by_property("genre", genre)
        genre_rules = [r.get("description", "") for r in rules_data if r.get("description")]

    # Mutation lineage
    mutation_lineage: list[str] | None = None
    mutation_ops = prog_meta.get("mutation_ops", [])
    if mutation_ops:
        mutation_lineage = [
            op.get("description", f"{op.get('operation', '?')}")
            for op in mutation_ops
        ]

    # Build prompt and call Gemini Pro
    user_prompt, system_prompt = explanation_prompt(
        chord_symbols=chord_symbols,
        roman_numerals=roman_numerals,
        key_center=key_center,
        mode=mode,
        genre=genre,
        genre_rules=genre_rules,
        scores=scores,
        mutation_lineage=mutation_lineage,
    )

    try:
        gemini_result = await gemini.generate_structured(
            user_prompt,
            GeminiExplanationOutput,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.exception("Gemini explanation generation failed for %s", candidate_id)
        raise HTTPException(
            status_code=504,
            detail="Explanation generation timed out. Try again.",
        ) from exc

    # Persist to Neo4j
    explanation = CandidateExplanation(
        id=f"ce_{ULID()}",
        type="candidate_explanation",
        status="active",
        session_id=session_id,
        candidate_id=candidate_id,
        summary=gemini_result.summary,
        why_it_works=gemini_result.why_it_works,
        what_is_experimental=gemini_result.what_is_experimental,
        recommended_use_cases=gemini_result.recommended_use_cases,
    )
    try:
        await explanation_repo.create(explanation)

        # Create relationship: (CandidateExplanation)-[:EXPLAINS]->(ArrangementCandidate)
        async with driver.session() as neo_session:
            await neo_session.run(
                """
                MATCH (e:CandidateExplanation {id: $eid})
                MATCH (a:ArrangementCandidate {id: $aid})
                MERGE (e)-[:EXPLAINS]->(a)
                """,
                eid=explanation.id,
                aid=candidate_id,
            )
    except Exception:
        logger.exception("Failed to persist explanation for %s", candidate_id)
        # Still return the result even if persistence fails

    return ExplanationResponse(
        summary=gemini_result.summary,
        why_it_works=gemini_result.why_it_works,
        what_is_experimental=gemini_result.what_is_experimental,
        recommended_use_cases=gemini_result.recommended_use_cases,
    )
```

- [ ] **Step 8: Register the explanations router in app.py**

In `backend/src/explorator/api/app.py`, add the import:

```python
from explorator.api.routes.explanations import router as explanations_router
```

And add this line after the existing `app.include_router(exports_router, prefix="/v1")`:

```python
    app.include_router(explanations_router, prefix="/v1")
```

- [ ] **Step 9: Run all explanation tests**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_explanation_api.py -v`
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/src/explorator/graph/candidate_explanation_repo.py backend/src/explorator/api/routes/explanations.py backend/src/explorator/api/app.py backend/tests/unit/engine/test_explanation_api.py
git commit -m "feat(m4b): add CandidateExplanation repo, API route with generate-or-cache pattern"
```

---

### Task 7: Comparison repo + API route

**Files:**
- Create: `backend/src/explorator/graph/comparison_view_repo.py`
- Create: `backend/src/explorator/api/routes/comparisons.py`
- Modify: `backend/src/explorator/api/app.py`
- Create: `backend/tests/unit/engine/test_comparison_api.py`

- [ ] **Step 1: Write failing tests for ComparisonViewRepo**

Create `backend/tests/unit/engine/test_comparison_api.py`:

```python
"""Tests for ComparisonView repo and API route."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from explorator.graph.comparison_view_repo import ComparisonViewRepo
from explorator.models.export import ComparisonView


class TestComparisonViewRepo:
    """Integration tests for ComparisonViewRepo."""

    @pytest_asyncio.fixture
    async def repo(self, neo4j_driver) -> ComparisonViewRepo:
        return ComparisonViewRepo(neo4j_driver)

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo: ComparisonViewRepo):
        view = ComparisonView(
            id="cv_test1",
            type="comparison_view",
            status="active",
            session_id="sess_test",
            candidate_ids=["arr_1", "arr_2"],
            comparison_axes=["voice_leading", "tension_curve"],
            labels={"arr_1": "A", "arr_2": "B"},
        )
        await repo.create(view)
        result = await repo.get_by_id("cv_test1")
        assert result is not None
        assert result["session_id"] == "sess_test"
        assert len(result["candidate_ids"]) == 2

    @pytest.mark.asyncio
    async def test_query_by_session(self, repo: ComparisonViewRepo):
        view = ComparisonView(
            id="cv_test2",
            type="comparison_view",
            status="active",
            session_id="sess_test2",
            candidate_ids=["arr_3"],
            comparison_axes=["playability"],
            labels={"arr_3": "C"},
        )
        await repo.create(view)
        results = await repo.query_by_property("session_id", "sess_test2")
        assert len(results) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_comparison_api.py::TestComparisonViewRepo -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement ComparisonViewRepo**

Create `backend/src/explorator/graph/comparison_view_repo.py`:

```python
"""Neo4j repository for ComparisonView entities."""

from explorator.graph.repository import BaseRepository


class ComparisonViewRepo(BaseRepository):
    """CRUD operations for ComparisonView nodes."""

    label = "ComparisonView"
```

- [ ] **Step 4: Run repo tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_comparison_api.py::TestComparisonViewRepo -v`
Expected: All 2 tests pass.

- [ ] **Step 5: Write failing tests for comparison API route**

Append to `backend/tests/unit/engine/test_comparison_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.comparisons import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestComparisonRoute:
    """Unit tests for comparison POST endpoint."""

    def test_post_comparison_returns_201(self):
        """POST creates a comparison and returns 201 with id."""
        app = _make_app()

        with patch(
            "explorator.api.routes.comparisons.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            mock_driver = MagicMock()
            mock_neo_session = AsyncMock()
            mock_driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_neo_session)
            mock_driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "explorator.api.routes.comparisons.ComparisonViewRepo"
            ) as MockRepo:
                MockRepo.return_value.create = AsyncMock()

                client = TestClient(app)
                resp = client.post(
                    "/v1/sessions/sess_1/comparisons",
                    json={
                        "candidate_ids": ["arr_1", "arr_2"],
                        "comparison_axes": ["voice_leading", "tension_curve"],
                        "labels": {"arr_1": "A", "arr_2": "B"},
                    },
                )
                assert resp.status_code == 201
                data = resp.json()
                assert "comparison_id" in data

    def test_post_comparison_requires_two_candidates(self):
        """POST with < 2 candidates returns 422."""
        app = _make_app()

        with patch(
            "explorator.api.routes.comparisons.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ):
            client = TestClient(app)
            resp = client.post(
                "/v1/sessions/sess_1/comparisons",
                json={
                    "candidate_ids": ["arr_1"],
                    "comparison_axes": [],
                    "labels": {},
                },
            )
            assert resp.status_code == 422
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_comparison_api.py::TestComparisonRoute -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 7: Implement comparison API route**

Create `backend/src/explorator/api/routes/comparisons.py`:

```python
"""Comparison API routes — record comparison events."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.api.deps import get_neo4j_driver
from explorator.graph.comparison_view_repo import ComparisonViewRepo
from explorator.models.export import ComparisonView

logger = logging.getLogger(__name__)
router = APIRouter(tags=["comparisons"])


class ComparisonRequestBody(BaseModel):
    """Request body for recording a comparison event."""

    candidate_ids: list[str]
    comparison_axes: list[str] = []
    labels: dict[str, str] = {}


@router.post("/sessions/{session_id}/comparisons", status_code=201)
async def record_comparison(
    session_id: str,
    body: ComparisonRequestBody,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, str]:
    """Record a comparison event for provenance.

    Returns 201 with the comparison_id. Frontend fires this as
    fire-and-forget (.catch logs only, never blocks UI).
    """
    if len(body.candidate_ids) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 candidate_ids required for comparison",
        )

    comparison_id = f"cv_{ULID()}"
    comparison = ComparisonView(
        id=comparison_id,
        type="comparison_view",
        status="active",
        session_id=session_id,
        candidate_ids=body.candidate_ids,
        comparison_axes=body.comparison_axes,
        labels=body.labels,
    )

    repo = ComparisonViewRepo(driver)
    try:
        await repo.create(comparison)

        # Create relationships: (ComparisonView)-[:COMPARES]->(ArrangementCandidate)
        async with driver.session() as neo_session:
            for cid in body.candidate_ids:
                await neo_session.run(
                    """
                    MATCH (cv:ComparisonView {id: $cv_id})
                    MATCH (ac:ArrangementCandidate {id: $ac_id})
                    MERGE (cv)-[:COMPARES]->(ac)
                    """,
                    cv_id=comparison_id,
                    ac_id=cid,
                )
    except Exception:
        logger.exception("Failed to persist comparison view %s", comparison_id)
        raise HTTPException(status_code=500, detail="Failed to record comparison") from None

    return {"comparison_id": comparison_id}
```

- [ ] **Step 8: Register the comparisons router in app.py**

In `backend/src/explorator/api/app.py`, add the import:

```python
from explorator.api.routes.comparisons import router as comparisons_router
```

And add this line after the explanations router:

```python
    app.include_router(comparisons_router, prefix="/v1")
```

- [ ] **Step 9: Run all comparison tests**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_comparison_api.py -v`
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add backend/src/explorator/graph/comparison_view_repo.py backend/src/explorator/api/routes/comparisons.py backend/src/explorator/api/app.py backend/tests/unit/engine/test_comparison_api.py
git commit -m "feat(m4b): add ComparisonView repo and fire-and-forget comparison POST endpoint"
```

---

### Task 8: Provenance API endpoint

**Files:**
- Modify: `backend/src/explorator/api/routes/sessions.py`
- Create: `backend/tests/unit/engine/test_provenance_api.py`

- [ ] **Step 1: Write failing tests for provenance endpoint**

Create `backend/tests/unit/engine/test_provenance_api.py`:

```python
"""Tests for the provenance GET endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from explorator.api.routes.sessions import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


class TestProvenanceEndpoint:
    """Tests for GET /sessions/{id}/provenance."""

    def test_provenance_returns_trace(self):
        app = _make_app()

        trace = {
            "id": "pt_1",
            "session_id": "sess_1",
            "events": [
                {"timestamp": "2026-04-12T00:00:00Z", "action": "generate", "object_id": "pc_1", "round_number": 1, "details": {}},
                {"timestamp": "2026-04-12T00:01:00Z", "action": "mutate", "object_id": "pc_2", "round_number": 2, "details": {}},
            ],
        }

        with patch(
            "explorator.api.routes.sessions.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "explorator.api.routes.sessions.ProvenanceTraceRepo"
        ) as MockRepo:
            MockRepo.return_value.get_by_session_id = AsyncMock(return_value=trace)

            client = TestClient(app)
            resp = client.get("/v1/sessions/sess_1/provenance")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["events"]) == 2
            assert data["events"][0]["action"] == "generate"

    def test_provenance_empty_when_no_trace(self):
        app = _make_app()

        with patch(
            "explorator.api.routes.sessions.get_neo4j_driver",
            new=AsyncMock(return_value=MagicMock()),
        ), patch(
            "explorator.api.routes.sessions.ProvenanceTraceRepo"
        ) as MockRepo:
            MockRepo.return_value.get_by_session_id = AsyncMock(return_value=None)

            client = TestClient(app)
            resp = client.get("/v1/sessions/sess_1/provenance")
            assert resp.status_code == 200
            data = resp.json()
            assert data["events"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_api.py -v`
Expected: FAIL (endpoint does not exist yet).

- [ ] **Step 3: Add provenance endpoint to sessions.py**

In `backend/src/explorator/api/routes/sessions.py`, add the import:

```python
from explorator.graph.provenance_trace_repo import ProvenanceTraceRepo
```

Then add the new endpoint after the existing `delete_session` function:

```python
class ProvenanceResponse(BaseModel):
    """Response for session provenance trace."""

    session_id: str
    events: list[dict]


@router.get("/sessions/{session_id}/provenance")
async def get_provenance(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> ProvenanceResponse:
    """Return the provenance trace for a session.

    Returns an empty events list if no trace exists yet
    (session hasn't been explored).
    """
    repo = ProvenanceTraceRepo(driver)
    trace = await repo.get_by_session_id(session_id)
    if trace is None:
        return ProvenanceResponse(session_id=session_id, events=[])
    return ProvenanceResponse(
        session_id=session_id,
        events=trace.get("events", []),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_provenance_api.py -v`
Expected: All 2 tests pass.

- [ ] **Step 5: Run full backend test suite**

Run: `cd backend && uv run python -m pytest tests/unit/ -v --timeout=30`
Expected: All tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/api/routes/sessions.py backend/tests/unit/engine/test_provenance_api.py
git commit -m "feat(m4b): add GET /sessions/{id}/provenance endpoint"
```

---

### Task 9: Frontend — Explain button on ArrangementCard

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/components/ArrangementCard.tsx`
- Modify: `frontend/src/components/ArrangementDetail.tsx`

- [ ] **Step 1: Add explanation types and API functions to api.ts**

In `frontend/src/services/api.ts`, add after the existing export types section:

```typescript
// --- M4b Explanation Types ---

export interface CandidateExplanation {
  summary: string;
  why_it_works: string[];
  what_is_experimental: string[];
  recommended_use_cases: string[];
}

export async function generateExplanation(candidateId: string): Promise<CandidateExplanation> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/explain`, {
    method: 'POST',
  });
  if (res.status === 504) throw new Error('Explanation generation timed out. Try again.');
  if (!res.ok) throw new Error(`Explanation failed: ${res.statusText}`);
  return res.json();
}

export async function getCachedExplanation(candidateId: string): Promise<CandidateExplanation | null> {
  const res = await fetch(`${API_BASE}/candidates/${candidateId}/explanation`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to get explanation: ${res.statusText}`);
  return res.json();
}
```

- [ ] **Step 2: Add provenance types and API functions to api.ts**

In `frontend/src/services/api.ts`, add:

```typescript
// --- M4b Provenance Types ---

export interface ProvenanceEvent {
  timestamp: string;
  action: string;
  object_id: string;
  round_number: number | null;
  details: Record<string, unknown>;
}

export interface ProvenanceResponse {
  session_id: string;
  events: ProvenanceEvent[];
}

export async function getProvenance(sessionId: string): Promise<ProvenanceResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/provenance`);
  if (!res.ok) throw new Error(`Failed to get provenance: ${res.statusText}`);
  return res.json();
}

// --- M4b Comparison Types ---

export async function recordComparison(
  sessionId: string,
  candidateIds: string[],
  comparisonAxes: string[],
  labels: Record<string, string>,
): Promise<void> {
  fetch(`${API_BASE}/sessions/${sessionId}/comparisons`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_ids: candidateIds,
      comparison_axes: comparisonAxes,
      labels,
    }),
  }).catch((err) => console.warn('Failed to record comparison:', err));
}
```

- [ ] **Step 3: Update ArrangementCard to include Explain button**

Replace the full content of `frontend/src/components/ArrangementCard.tsx` with:

```tsx
import { useState } from "react"
import type { ArrangementSummary, CandidateExplanation } from "../services/api"
import { generateExplanation } from "../services/api"

interface ArrangementCardProps {
  arrangement: ArrangementSummary
  selected: boolean
  onClick: () => void
  genre: string
}

const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "border-violet-500",
  synthwave: "border-pink-500",
  cinematic: "border-yellow-500",
}

function getAccentBorder(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}

function scoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}

function parseBadges(rationale: string): { voicing: string; bass: string } | null {
  const parts = rationale.split(" + ")
  if (parts.length < 2) return null
  return { voicing: parts[0].trim(), bass: parts[1].trim() }
}

export default function ArrangementCard({
  arrangement,
  selected,
  onClick,
  genre,
}: ArrangementCardProps) {
  const isRejected = arrangement.status === "rejected"
  const badges = parseBadges(arrangement.rationale)
  const accentBorder = getAccentBorder(genre)

  const [explanation, setExplanation] = useState<CandidateExplanation | null>(null)
  const [explaining, setExplaining] = useState(false)
  const [explainError, setExplainError] = useState<string | null>(null)
  const [showExplanation, setShowExplanation] = useState(false)

  const handleExplain = async (e: React.MouseEvent) => {
    e.stopPropagation()

    if (explanation) {
      setShowExplanation(!showExplanation)
      return
    }

    setExplaining(true)
    setExplainError(null)
    try {
      const result = await generateExplanation(arrangement.id)
      setExplanation(result)
      setShowExplanation(true)
    } catch (err) {
      setExplainError(err instanceof Error ? err.message : "Failed to generate explanation")
    } finally {
      setExplaining(false)
    }
  }

  return (
    <div
      onClick={onClick}
      className={[
        "border rounded-md p-3 cursor-pointer transition-all",
        selected
          ? `border-l-4 ${accentBorder} bg-slate-800 border-slate-700`
          : "border-slate-700 bg-slate-900 hover:bg-slate-800",
        isRejected ? "opacity-40" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Score */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-500 text-xs">
          #{arrangement.rank_within_round}
        </span>
        <span className={`text-sm font-bold font-mono ${scoreColor(arrangement.weighted_total)}`}>
          {(arrangement.weighted_total ?? 0).toFixed(2)}
        </span>
      </div>

      {/* Badges */}
      {badges ? (
        <div className="flex flex-wrap gap-1">
          <span className="text-xs bg-amber-400/10 text-amber-400 px-1.5 py-0.5 rounded font-mono">
            {badges.voicing}
          </span>
          <span className="text-xs bg-cyan-400/10 text-cyan-400 px-1.5 py-0.5 rounded font-mono">
            {badges.bass}
          </span>
        </div>
      ) : (
        <p className="text-slate-500 text-xs truncate">{arrangement.rationale}</p>
      )}

      {/* Explain button */}
      {!isRejected && (
        <button
          onClick={handleExplain}
          disabled={explaining}
          className="mt-2 text-xs px-2 py-1 rounded border border-slate-600 text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors disabled:opacity-50"
        >
          {explaining ? (
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full animate-spin" />
              Generating...
            </span>
          ) : explanation ? (
            showExplanation ? "Hide explanation" : "Show explanation"
          ) : (
            "Explain"
          )}
        </button>
      )}

      {/* Explain error */}
      {explainError && (
        <p className="mt-1 text-xs text-rose-400">{explainError}</p>
      )}

      {/* Explanation display */}
      {showExplanation && explanation && (
        <div className="mt-2 pt-2 border-t border-slate-700 text-xs space-y-2">
          <p className="text-slate-300 italic">{explanation.summary}</p>

          {explanation.why_it_works.length > 0 && (
            <div>
              <span className="text-emerald-400 font-medium">Why it works:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
                {explanation.why_it_works.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.what_is_experimental.length > 0 && (
            <div>
              <span className="text-amber-400 font-medium">Experimental:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
                {explanation.what_is_experimental.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {explanation.recommended_use_cases.length > 0 && (
            <div>
              <span className="text-violet-400 font-medium">Best for:</span>
              <ul className="list-disc list-inside text-slate-400 mt-0.5">
                {explanation.recommended_use_cases.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Build frontend to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/components/ArrangementCard.tsx
git commit -m "feat(m4b): add Explain button on ArrangementCard with generate-or-cache API"
```

---

### Task 10: Frontend — ComparisonView + SessionHistory + candidateStore updates

**Files:**
- Modify: `frontend/src/stores/candidateStore.ts`
- Modify: `frontend/src/components/PianoRoll.tsx`
- Create: `frontend/src/components/ComparisonView.tsx`
- Create: `frontend/src/components/SessionHistory.tsx`
- Modify: `frontend/src/views/SessionWorkspace.tsx`

- [ ] **Step 1: Add comparison selection to candidateStore**

Replace `frontend/src/stores/candidateStore.ts` with:

```typescript
import { create } from 'zustand';
import type { CandidateSummary, FinalSelection } from '../services/api';

interface CandidateState {
  candidates: CandidateSummary[];
  finalSelection: FinalSelection | null;
  loading: boolean;
  progress: string | null;
  error: string | null;
  selectedForComparison: Set<string>;
  setCandidates: (candidates: CandidateSummary[]) => void;
  setFinalSelection: (fs: FinalSelection | null) => void;
  setLoading: (loading: boolean) => void;
  setProgress: (progress: string | null) => void;
  setError: (error: string | null) => void;
  toggleComparison: (candidateId: string) => void;
  clearComparison: () => void;
  reset: () => void;
}

const MAX_COMPARISON = 3;

export const useCandidateStore = create<CandidateState>((set) => ({
  candidates: [],
  finalSelection: null,
  loading: false,
  progress: null,
  error: null,
  selectedForComparison: new Set<string>(),
  setCandidates: (candidates) => set({ candidates }),
  setFinalSelection: (finalSelection) => set({ finalSelection }),
  setLoading: (loading) => set({ loading }),
  setProgress: (progress) => set({ progress }),
  setError: (error) => set({ error }),
  toggleComparison: (candidateId) =>
    set((state) => {
      const next = new Set(state.selectedForComparison);
      if (next.has(candidateId)) {
        next.delete(candidateId);
      } else {
        if (next.size >= MAX_COMPARISON) {
          // Remove oldest (first inserted)
          const oldest = next.values().next().value;
          if (oldest !== undefined) next.delete(oldest);
        }
        next.add(candidateId);
      }
      return { selectedForComparison: next };
    }),
  clearComparison: () => set({ selectedForComparison: new Set<string>() }),
  reset: () =>
    set({
      candidates: [],
      finalSelection: null,
      loading: false,
      progress: null,
      error: null,
      selectedForComparison: new Set<string>(),
    }),
}));
```

- [ ] **Step 2: Parameterize PianoRoll for compact mode**

Replace `frontend/src/components/PianoRoll.tsx` with:

```tsx
import { useEffect, useRef } from "react"
import type { ArrangementDetail } from "../services/api"
import { pitchToMidi, midiToPitchLabel } from "../services/midiUtils"
import { useAudioStore } from "../stores/audioStore"

interface PianoRollProps {
  arrangement: ArrangementDetail
  genre: string
  compact?: boolean
  showCursor?: boolean
  barWidth?: number
}

const DEFAULT_BAR_WIDTH = 90
const DEFAULT_ROW_HEIGHT = 8
const COMPACT_ROW_HEIGHT = 4
const LABEL_WIDTH = 48
const HEADER_HEIGHT = 24

const GENRE_ACCENT: Record<string, string> = {
  dream_pop: "#a78bfa",
  synthwave: "#f472b6",
  cinematic: "#eab308",
}

function getAccent(genre: string): string {
  const key = genre.toLowerCase().replace(/[\s-]/g, "_")
  return GENRE_ACCENT[key] ?? GENRE_ACCENT["dream_pop"]
}

function collectMidiValues(arrangement: ArrangementDetail): number[] {
  const midis: number[] = []
  arrangement.voicing_plan?.voicing_events.forEach((ev) => {
    ev.pitches.forEach((p) => midis.push(pitchToMidi(p)))
  })
  arrangement.bass_line?.note_events.forEach((ev) => {
    midis.push(pitchToMidi(ev.pitch))
  })
  return midis
}

export default function PianoRoll({
  arrangement,
  genre,
  compact = false,
  showCursor = true,
  barWidth: barWidthProp,
}: PianoRollProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Only subscribe to audio store when cursor is shown
  const audioState = showCursor ? useAudioStore() : { playing: false, currentPosition: 0, mutedTracks: { voicing: false, bass: false } }
  const { playing, currentPosition, mutedTracks } = audioState

  const BAR_WIDTH = barWidthProp ?? DEFAULT_BAR_WIDTH
  const ROW_HEIGHT = compact ? COMPACT_ROW_HEIGHT : DEFAULT_ROW_HEIGHT

  const voicingEvents = arrangement.voicing_plan?.voicing_events ?? []
  const bassEvents = arrangement.bass_line?.note_events ?? []
  const hasEvents = voicingEvents.length > 0 || bassEvents.length > 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1

    // Calculate MIDI range
    const midiValues = collectMidiValues(arrangement)
    const octavePad = compact ? 6 : 12
    const minMidi = midiValues.length > 0 ? Math.min(...midiValues) - octavePad : 48
    const maxMidi = midiValues.length > 0 ? Math.max(...midiValues) + octavePad : 84

    // Calculate total bars
    const allBars = [
      ...voicingEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
      ...bassEvents.map((e) => e.bar + Math.ceil(e.duration_beats / 4)),
    ]
    const totalBars = allBars.length > 0 ? Math.max(...allBars) : 8

    const rows = maxMidi - minMidi + 1
    const canvasWidth = LABEL_WIDTH + totalBars * BAR_WIDTH
    const canvasHeight = HEADER_HEIGHT + rows * ROW_HEIGHT

    // Set canvas logical and physical size
    canvas.width = canvasWidth * dpr
    canvas.height = canvasHeight * dpr
    canvas.style.width = `${canvasWidth}px`
    canvas.style.height = `${canvasHeight}px`
    ctx.scale(dpr, dpr)

    // Background
    ctx.fillStyle = "#0f172a"
    ctx.fillRect(0, 0, canvasWidth, canvasHeight)

    // Draw horizontal pitch rows
    for (let midi = minMidi; midi <= maxMidi; midi++) {
      const noteInOctave = midi % 12
      const isBlackKey = [1, 3, 6, 8, 10].includes(noteInOctave)
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT

      if (isBlackKey) {
        ctx.fillStyle = "#1e293b"
        ctx.fillRect(LABEL_WIDTH, y, totalBars * BAR_WIDTH, ROW_HEIGHT)
      }
    }

    // Draw beat and bar grid lines
    for (let bar = 0; bar <= totalBars; bar++) {
      for (let beat = 0; beat < 4; beat++) {
        const x = LABEL_WIDTH + bar * BAR_WIDTH + beat * (BAR_WIDTH / 4)
        if (beat === 0) {
          ctx.strokeStyle = "#334155"
          ctx.lineWidth = 1
        } else {
          ctx.strokeStyle = "#1e293b"
          ctx.lineWidth = 0.5
        }
        ctx.beginPath()
        ctx.moveTo(x, HEADER_HEIGHT)
        ctx.lineTo(x, canvasHeight)
        ctx.stroke()
      }
    }

    // Header background
    ctx.fillStyle = "#0f172a"
    ctx.fillRect(0, 0, canvasWidth, HEADER_HEIGHT)

    // Bar numbers in header
    ctx.fillStyle = "#64748b"
    ctx.font = compact ? "8px monospace" : "10px monospace"
    ctx.textAlign = "center"
    for (let bar = 1; bar <= totalBars; bar++) {
      const x = LABEL_WIDTH + (bar - 1) * BAR_WIDTH + BAR_WIDTH / 2
      ctx.fillText(`${bar}`, x, HEADER_HEIGHT - 6)
    }

    // Pitch labels on left edge
    if (!compact) {
      ctx.textAlign = "right"
      ctx.font = "9px monospace"
      for (let midi = minMidi; midi <= maxMidi; midi++) {
        if (midi % 12 === 0) {
          const label = midiToPitchLabel(midi)
          const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + ROW_HEIGHT - 1
          ctx.fillStyle = "#94a3b8"
          ctx.fillText(label, LABEL_WIDTH - 4, y)
        }
      }
    }

    // Draw voicing notes
    const voicingOpacity = mutedTracks.voicing ? 0.2 : 1.0
    ctx.globalAlpha = voicingOpacity
    for (const ev of voicingEvents) {
      const x = LABEL_WIDTH + (ev.bar + (ev.beat - 1) / 4) * BAR_WIDTH
      const noteWidth = Math.max(compact ? 2 : 4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      for (const pitch of ev.pitches) {
        const midi = pitchToMidi(pitch)
        if (midi < minMidi || midi > maxMidi) continue
        const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1

        ctx.fillStyle = "#fbbf24"
        ctx.beginPath()
        ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, compact ? 1 : 2)
        ctx.fill()
      }
    }
    ctx.globalAlpha = 1.0

    // Draw bass notes
    const bassOpacity = mutedTracks.bass ? 0.2 : 1.0
    ctx.globalAlpha = bassOpacity
    for (const ev of bassEvents) {
      const midi = pitchToMidi(ev.pitch)
      if (midi < minMidi || midi > maxMidi) continue
      const x = LABEL_WIDTH + (ev.bar + (ev.beat - 1) / 4) * BAR_WIDTH
      const y = HEADER_HEIGHT + (maxMidi - midi) * ROW_HEIGHT + 1
      const noteWidth = Math.max(compact ? 2 : 4, (ev.duration_beats / 4) * BAR_WIDTH - 2)

      ctx.fillStyle = "#22d3ee"
      ctx.beginPath()
      ctx.roundRect(x, y, noteWidth, ROW_HEIGHT - 2, compact ? 1 : 2)
      ctx.fill()
    }
    ctx.globalAlpha = 1.0

    // Playback cursor
    if (showCursor && playing) {
      const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
      ctx.strokeStyle = getAccent(genre)
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cursorX, 0)
      ctx.lineTo(cursorX, canvasHeight)
      ctx.stroke()
    }
  }, [arrangement, currentPosition, playing, mutedTracks, genre, voicingEvents, bassEvents, BAR_WIDTH, ROW_HEIGHT, compact, showCursor])

  // Auto-scroll to keep cursor in view
  useEffect(() => {
    if (!showCursor || !playing || !containerRef.current) return
    const container = containerRef.current
    const cursorX = LABEL_WIDTH + currentPosition * BAR_WIDTH
    const scrollLeft = container.scrollLeft
    const viewWidth = container.clientWidth

    if (cursorX > scrollLeft + viewWidth - 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    } else if (cursorX < scrollLeft + 80) {
      container.scrollLeft = cursorX - viewWidth / 2
    }
  }, [currentPosition, playing, showCursor, BAR_WIDTH])

  if (!hasEvents) {
    return (
      <div className={`flex items-center justify-center ${compact ? "h-24" : "h-48"} bg-slate-900 text-slate-500 text-sm`}>
        No events to display
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="overflow-x-auto overflow-y-auto bg-slate-900"
      style={{ maxHeight: compact ? "150px" : "400px" }}
    >
      <canvas ref={canvasRef} />
    </div>
  )
}
```

- [ ] **Step 3: Create ComparisonView component**

Create `frontend/src/components/ComparisonView.tsx`:

```tsx
import { useEffect } from "react"
import type { ArrangementDetail } from "../services/api"
import { recordComparison } from "../services/api"
import { useCandidateStore } from "../stores/candidateStore"
import { useArrangementStore } from "../stores/arrangementStore"
import PianoRoll from "./PianoRoll"

interface ComparisonViewProps {
  sessionId: string
  genre: string
  arrangements: Map<string, ArrangementDetail>
  onClose: () => void
}

const SCORE_DIMENSIONS = [
  "voice_leading",
  "tension_curve",
  "playability",
  "register_density",
  "genre_fit",
  "novelty",
]

function dimensionLabel(dim: string): string {
  return dim
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

function scoreColor(score: number): string {
  if (score >= 8) return "text-emerald-400"
  if (score >= 6) return "text-amber-400"
  return "text-rose-400"
}

export default function ComparisonView({
  sessionId,
  genre,
  arrangements,
  onClose,
}: ComparisonViewProps) {
  const { selectedForComparison, clearComparison } = useCandidateStore()

  const candidateIds = Array.from(selectedForComparison)
  const comparedArrangements = candidateIds
    .map((id) => arrangements.get(id))
    .filter((a): a is ArrangementDetail => a !== undefined)

  // Fire-and-forget comparison recording
  useEffect(() => {
    if (comparedArrangements.length >= 2) {
      const labels: Record<string, string> = {}
      comparedArrangements.forEach((a, i) => {
        labels[a.id] = String.fromCharCode(65 + i) // A, B, C
      })
      recordComparison(
        sessionId,
        candidateIds,
        SCORE_DIMENSIONS,
        labels,
      )
    }
  }, [candidateIds.join(",")])

  if (comparedArrangements.length < 2) {
    return (
      <div className="p-4 text-center text-slate-500 text-sm">
        Select at least 2 candidates to compare.
      </div>
    )
  }

  // Collect all scores for leader highlighting
  const allScores: Record<string, Record<string, number>> = {}
  comparedArrangements.forEach((a) => {
    allScores[a.id] = a.scorecard?.scores ?? {}
  })

  const leaders: Record<string, string> = {}
  SCORE_DIMENSIONS.forEach((dim) => {
    let bestId = ""
    let bestScore = -1
    comparedArrangements.forEach((a) => {
      const s = allScores[a.id]?.[dim] ?? 0
      if (s > bestScore) {
        bestScore = s
        bestId = a.id
      }
    })
    if (bestId) leaders[dim] = bestId
  })

  return (
    <div className="bg-slate-950 rounded-lg border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 bg-slate-900">
        <span className="text-sm font-medium text-slate-300">
          Comparing {comparedArrangements.length} candidates
        </span>
        <button
          onClick={() => {
            clearComparison()
            onClose()
          }}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          Close
        </button>
      </div>

      {/* Stacked piano rolls */}
      <div className="divide-y divide-slate-800">
        {comparedArrangements.map((a, i) => (
          <div key={a.id} className="flex">
            <div className="w-16 flex-shrink-0 flex flex-col items-center justify-center bg-slate-900 border-r border-slate-800 py-2">
              <span className="text-lg font-bold text-slate-300">
                {String.fromCharCode(65 + i)}
              </span>
              <span className="text-xs text-slate-500 mt-0.5">
                {(a.scorecard?.weighted_total ?? a.weighted_total ?? 0).toFixed(1)}
              </span>
            </div>
            <div className="flex-1">
              <PianoRoll
                arrangement={a}
                genre={genre}
                compact
                showCursor={false}
                barWidth={70}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Score comparison table */}
      <div className="p-4 border-t border-slate-700">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
          Score Comparison
        </h3>
        <div className="space-y-1">
          {SCORE_DIMENSIONS.map((dim) => (
            <div key={dim} className="flex items-center text-xs">
              <span className="w-32 text-slate-500 truncate">
                {dimensionLabel(dim)}
              </span>
              <div className="flex-1 flex gap-4">
                {comparedArrangements.map((a, i) => {
                  const score = allScores[a.id]?.[dim] ?? 0
                  const isLeader = leaders[dim] === a.id
                  return (
                    <span
                      key={a.id}
                      className={`font-mono ${scoreColor(score)} ${isLeader ? "font-bold" : "opacity-70"}`}
                    >
                      {String.fromCharCode(65 + i)}: {score.toFixed(1)}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create SessionHistory component**

Create `frontend/src/components/SessionHistory.tsx`:

```tsx
import { useEffect, useRef, useState } from "react"
import type { ProvenanceEvent } from "../services/api"
import { getProvenance } from "../services/api"

interface SessionHistoryProps {
  sessionId: string
}

const ACTION_ICONS: Record<string, string> = {
  generate: "G",
  mutate: "M",
  feedback: "F",
  rank_and_select: "R",
  export: "E",
}

const ACTION_COLORS: Record<string, string> = {
  generate: "bg-violet-500",
  mutate: "bg-amber-500",
  feedback: "bg-cyan-500",
  rank_and_select: "bg-emerald-500",
  export: "bg-pink-500",
}

function formatTime(timestamp: string): string {
  try {
    const d = new Date(timestamp)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  } catch {
    return ""
  }
}

function describeEvent(event: ProvenanceEvent): string {
  const details = event.details as Record<string, unknown>
  switch (event.action) {
    case "generate":
      return `Generated ${details.candidate_count ?? "?"} candidates`
    case "mutate":
      return `Mutated ${(details.source_candidate_id as string)?.slice(-6) ?? "?"} -> ${(details.result_candidate_id as string)?.slice(-6) ?? "?"}`
    case "feedback":
      return `Feedback loaded (${details.feedback_count ?? 0} items)`
    case "rank_and_select": {
      const roles = details.role_assignments as Record<string, string> | undefined
      const count = roles ? Object.keys(roles).length : details.selected_count ?? "?"
      return `Ranked finalists (${count} selected)`
    }
    case "export":
      return `Exported candidates`
    default:
      return event.action
  }
}

export default function SessionHistory({ sessionId }: SessionHistoryProps) {
  const [events, setEvents] = useState<ProvenanceEvent[]>([])
  const [collapsed, setCollapsed] = useState(true)
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const fetchEvents = async () => {
    setLoading(true)
    try {
      const data = await getProvenance(sessionId)
      setEvents(data.events)
    } catch {
      // Silently fail — provenance is non-critical
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [sessionId])

  // Auto-scroll to newest
  useEffect(() => {
    if (!collapsed && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events, collapsed])

  if (events.length === 0 && !loading) return null

  return (
    <div className="rounded-lg border border-slate-700 overflow-hidden">
      <button
        onClick={() => {
          if (collapsed) fetchEvents()
          setCollapsed(!collapsed)
        }}
        className="w-full flex items-center justify-between px-4 py-2 bg-slate-900 hover:bg-slate-800 transition-colors"
      >
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          Session History ({events.length})
        </span>
        <span className="text-slate-500 text-xs">
          {collapsed ? "Show" : "Hide"}
        </span>
      </button>

      {!collapsed && (
        <div
          ref={scrollRef}
          className="max-h-64 overflow-y-auto bg-slate-950 p-3"
        >
          {loading && events.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-4">Loading...</p>
          ) : (
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-start gap-2">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center mt-0.5">
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white ${ACTION_COLORS[event.action] ?? "bg-slate-600"}`}
                    >
                      {ACTION_ICONS[event.action] ?? "?"}
                    </div>
                    {i < events.length - 1 && (
                      <div className="w-px h-4 bg-slate-700 mt-0.5" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-slate-300">
                      {describeEvent(event)}
                    </p>
                    <div className="flex gap-2 text-[10px] text-slate-500">
                      {event.round_number != null && (
                        <span>Round {event.round_number}</span>
                      )}
                      <span>{formatTime(event.timestamp)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Wire ComparisonView and SessionHistory into SessionWorkspace**

In `frontend/src/views/SessionWorkspace.tsx`, add imports at the top:

```typescript
import ComparisonView from '../components/ComparisonView';
import SessionHistory from '../components/SessionHistory';
import { getArrangement } from '../services/api';
import type { ArrangementDetail } from '../services/api';
```

Add state variables after existing state declarations:

```typescript
const [showComparison, setShowComparison] = useState(false);
const [comparisonArrangements, setComparisonArrangements] = useState<Map<string, ArrangementDetail>>(new Map());
```

Destructure `selectedForComparison` from the candidate store (update the existing destructure):

```typescript
const { candidates, setCandidates, selectedForComparison } = useCandidateStore();
```

Add a handler function for opening comparison view (after existing handlers):

```typescript
const handleCompare = async () => {
  const ids = Array.from(selectedForComparison);
  const loaded = new Map<string, ArrangementDetail>();
  for (const id of ids) {
    try {
      const detail = await getArrangement(id);
      loaded.set(id, detail);
    } catch {
      // skip failed loads
    }
  }
  setComparisonArrangements(loaded);
  setShowComparison(true);
};
```

In the realization view section (the `viewMode === 'realization'` branch), add a Compare button and the ComparisonView. Insert before the closing `</>` of the realization branch:

```tsx
{/* Compare button — appears when 2+ candidates selected */}
{selectedForComparison.size >= 2 && !showComparison && (
  <button
    onClick={handleCompare}
    className="fixed bottom-6 right-6 rounded-lg px-4 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-500 text-white shadow-lg z-10"
  >
    Compare {selectedForComparison.size}
  </button>
)}

{/* Comparison view */}
{showComparison && (
  <ComparisonView
    sessionId={id!}
    genre={session?.genre || 'dream_pop'}
    arrangements={comparisonArrangements}
    onClose={() => setShowComparison(false)}
  />
)}
```

At the bottom of the JSX (before the final closing `</div>`), add the SessionHistory:

```tsx
{/* Session history */}
{id && <SessionHistory sessionId={id} />}
```

- [ ] **Step 6: Build frontend to verify**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/candidateStore.ts frontend/src/components/PianoRoll.tsx frontend/src/components/ComparisonView.tsx frontend/src/components/SessionHistory.tsx frontend/src/views/SessionWorkspace.tsx
git commit -m "feat(m4b): add ComparisonView, SessionHistory, PianoRoll compact mode, candidateStore comparison selection"
```

---

### Final verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && uv run python -m pytest tests/unit/ -v --timeout=30`
Expected: All tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Clean build, no errors.

- [ ] **Step 3: Verify git log shows all M4b commits**

Run: `git log --oneline -15`
Expected: 10 commits with `feat(m4b):` prefix.
