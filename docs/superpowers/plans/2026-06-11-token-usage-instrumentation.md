# Token Usage Instrumentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture Gemini token usage at the adapter choke point and surface per-round, per-phase, and session-cumulative token counts + estimated cost to users in the session workspace.

**Architecture:** A `contextvars`-scoped accumulator (`RoundUsage`) collects usage recorded by the Gemini adapter after every call. The round route opens the scope around `graph.ainvoke`; a central node wrapper in `graph.py` tags the active phase and emits live `token_usage` SSE events; the route emits a terminal one. The frontend stores live + committed usage and renders a `TokenUsagePanel`.

**Tech Stack:** Python 3.13 / FastAPI / LangGraph / google-genai / pytest-asyncio (backend); React / TypeScript / Zustand / Vitest (frontend).

---

## File Structure

**Backend**
- Create `backend/src/explorator/adapters/usage.py` — accumulator, contextvars, `record`/`track_usage`/`set_phase`/`current_usage`, pricing + cost, `to_event`.
- Modify `backend/src/explorator/config.py` — pricing settings.
- Modify `backend/src/explorator/adapters/gemini.py` — `usage.record(...)` after each call.
- Modify `backend/src/explorator/adapters/gemini_mock.py` — synthetic `record_tokens`.
- Modify `backend/src/explorator/engine/graph.py` — `_instrument` wrapper at node registration.
- Modify `backend/src/explorator/api/routes/rounds.py` — `track_usage` scope + terminal event.
- Modify `backend/src/explorator/api/routes/genre_research.py` — `track_usage` scope + terminal event.
- Create `backend/tests/unit/adapters/test_usage.py`.
- Create `backend/tests/api/test_token_usage_event.py`.

**Frontend**
- Modify `frontend/src/services/sse.ts` — event union + `TokenUsage` type.
- Modify `frontend/src/stores/candidateStore.ts` — `usages`/`live`, setters, cumulative.
- Modify `frontend/src/hooks/useGenerationFlow.ts` — handle `token_usage`.
- Create `frontend/src/components/TokenUsagePanel.tsx`.
- Modify `frontend/src/views/SessionWorkspace.tsx` — render panel.
- Create `frontend/src/stores/__tests__/tokenUsageStore.test.ts`.
- Create `frontend/src/components/__tests__/TokenUsagePanel.test.tsx`.

---

## Task 1: Usage accumulator core (`usage.py`)

**Files:**
- Create: `backend/src/explorator/adapters/usage.py`
- Test: `backend/tests/unit/adapters/test_usage.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/adapters/test_usage.py
"""Tests for the token-usage accumulator."""

from types import SimpleNamespace

from explorator.adapters import usage


def test_record_tokens_is_noop_without_scope() -> None:
    # No active track_usage() scope → must not raise and must record nothing.
    usage.record_tokens("gemini-pro-latest", 100, 50)
    assert usage.current_usage() is None


def test_track_usage_aggregates_by_model_and_phase() -> None:
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 1000, 500)
        with usage.set_phase("evaluate_progressions"):
            usage.record_tokens("gemini-flash-latest", 200, 80)
            usage.record_tokens("gemini-flash-latest", 100, 40)

    totals = u.totals()
    assert totals == {"input": 1300, "output": 620, "cached": 0, "total": 1920}
    assert u.by_model["pro"].calls == 1
    assert u.by_model["flash"].calls == 2
    assert u.by_phase["generate"].model == "pro"
    assert u.by_phase["evaluate_progressions"].calls == 2


def test_record_reads_usage_metadata_none_safe() -> None:
    meta = SimpleNamespace(
        prompt_token_count=10,
        candidates_token_count=None,  # must coerce to 0
        cached_content_token_count=4,
    )
    with usage.track_usage() as u:
        usage.record("gemini-flash-latest", meta)
    assert u.totals() == {"input": 10, "output": 0, "cached": 4, "total": 14}


def test_estimated_cost_matches_pricing() -> None:
    # Defaults: pro input 1.25/M, pro output 10.0/M.
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 1000, 500)
    # (1000/1e6*1.25) + (500/1e6*10.0) = 0.00125 + 0.005 = 0.00625
    assert round(u.estimated_cost_usd(), 6) == 0.00625


def test_changed_since_last_emit_tracks_growth() -> None:
    with usage.track_usage() as u:
        assert u.changed_since_last_emit() is False  # nothing yet
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 10, 5)
        assert u.changed_since_last_emit() is True
        assert u.changed_since_last_emit() is False  # no new tokens since


def test_to_event_shape() -> None:
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 100, 40)
    event = u.to_event(round_number=2)
    assert event["round"] == 2
    assert event["total_input"] == 100
    assert event["total_output"] == 40
    assert event["total_tokens"] == 140
    assert event["by_model"]["pro"] == {"input": 100, "output": 40, "cached": 0, "calls": 1}
    assert event["by_phase"]["generate"]["model"] == "pro"
    assert event["is_estimate"] is True
    assert isinstance(event["estimated_cost_usd"], float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'explorator.adapters.usage'`

- [ ] **Step 3: Write the implementation**

```python
# backend/src/explorator/adapters/usage.py
"""Context-scoped Gemini token-usage accumulator.

Every Gemini call funnels through ``adapters/gemini.py``; that adapter records
usage here. A round handler opens a scope with ``track_usage()`` around
``graph.ainvoke``; the graph node wrapper tags the active phase via
``set_phase()``. contextvars copy by reference into asyncio child tasks, so a
parallel ``asyncio.gather`` fan-out aggregates into the one accumulator.

``record*`` is a no-op when no scope is active, so calls outside a round (or in
unit tests without a scope) are safe.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from explorator.config import settings


def _tier_of(model_name: str) -> str:
    """Collapse a concrete/aliased model name to a stable tier label."""
    return "flash" if "flash" in model_name.lower() else "pro"


@dataclass
class _ModelUsage:
    input: int = 0
    output: int = 0
    cached: int = 0
    calls: int = 0


@dataclass
class _PhaseUsage:
    input: int = 0
    output: int = 0
    cached: int = 0
    calls: int = 0
    model: str = ""


@dataclass
class RoundUsage:
    """Aggregated token usage for a single scoped run (one generate action)."""

    by_model: dict[str, _ModelUsage] = field(default_factory=dict)
    by_phase: dict[str, _PhaseUsage] = field(default_factory=dict)
    _last_emitted_total: int = 0

    def add(self, model_name: str, input_: int, output: int, cached: int, phase: str) -> None:
        tier = _tier_of(model_name)
        m = self.by_model.setdefault(tier, _ModelUsage())
        m.input += input_
        m.output += output
        m.cached += cached
        m.calls += 1
        p = self.by_phase.setdefault(phase, _PhaseUsage())
        p.input += input_
        p.output += output
        p.cached += cached
        p.calls += 1
        p.model = tier

    def totals(self) -> dict[str, int]:
        input_ = sum(m.input for m in self.by_model.values())
        output = sum(m.output for m in self.by_model.values())
        cached = sum(m.cached for m in self.by_model.values())
        return {"input": input_, "output": output, "cached": cached, "total": input_ + output + cached}

    def estimated_cost_usd(self) -> float:
        rates = _pricing()
        cost = 0.0
        for tier, m in self.by_model.items():
            r = rates[tier]
            cost += (m.input + m.cached) / 1_000_000 * r["input"]
            cost += m.output / 1_000_000 * r["output"]
        return cost

    def changed_since_last_emit(self) -> bool:
        total = self.totals()["total"]
        if total > self._last_emitted_total:
            self._last_emitted_total = total
            return True
        return False

    def to_event(self, round_number: int) -> dict[str, Any]:
        totals = self.totals()
        return {
            "round": round_number,
            "total_input": totals["input"],
            "total_output": totals["output"],
            "total_cached": totals["cached"],
            "total_tokens": totals["total"],
            "by_model": {
                tier: {"input": m.input, "output": m.output, "cached": m.cached, "calls": m.calls}
                for tier, m in self.by_model.items()
            },
            "by_phase": {
                name: {"input": p.input, "output": p.output, "calls": p.calls, "model": p.model}
                for name, p in self.by_phase.items()
            },
            "estimated_cost_usd": round(self.estimated_cost_usd(), 6),
            "is_estimate": True,
        }


_current: contextvars.ContextVar[RoundUsage | None] = contextvars.ContextVar(
    "explorator_token_usage", default=None
)
_current_phase: contextvars.ContextVar[str] = contextvars.ContextVar(
    "explorator_token_phase", default="unknown"
)


def _pricing() -> dict[str, dict[str, float]]:
    """USD per 1M tokens, per tier. Cached priced at the input rate."""
    return {
        "pro": {"input": settings.gemini_price_pro_input, "output": settings.gemini_price_pro_output},
        "flash": {"input": settings.gemini_price_flash_input, "output": settings.gemini_price_flash_output},
    }


def current_usage() -> RoundUsage | None:
    """Return the active accumulator, or None when outside a scope."""
    return _current.get()


@contextlib.contextmanager
def track_usage() -> Iterator[RoundUsage]:
    """Open an accumulator scope. Yields the fresh RoundUsage."""
    accumulator = RoundUsage()
    token = _current.set(accumulator)
    try:
        yield accumulator
    finally:
        _current.reset(token)


@contextlib.contextmanager
def set_phase(name: str) -> Iterator[None]:
    """Tag the active phase for attribution while the body runs."""
    token = _current_phase.set(name)
    try:
        yield
    finally:
        _current_phase.reset(token)


def record_tokens(model_name: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
    """Add raw token counts to the active accumulator. No-op outside a scope."""
    accumulator = _current.get()
    if accumulator is None:
        return
    accumulator.add(model_name, input_tokens, output_tokens, cached_tokens, _current_phase.get())


def record(model_name: str, usage_metadata: Any) -> None:
    """Extract counts from a google-genai ``usage_metadata`` object (None-safe)."""
    if usage_metadata is None:
        return
    record_tokens(
        model_name,
        getattr(usage_metadata, "prompt_token_count", 0) or 0,
        getattr(usage_metadata, "candidates_token_count", 0) or 0,
        getattr(usage_metadata, "cached_content_token_count", 0) or 0,
    )
```

- [ ] **Step 4: Add pricing settings to config (Task 1 depends on these)**

In `backend/src/explorator/config.py`, add inside the `Settings` class after the `# Gemini` block (after line 19, `gemini_flash_model`):

```python
    # Gemini pricing (USD per 1M tokens) — defaults are estimates; the models are
    # *-latest aliases, so cost is surfaced as "~ estimate". Override via env.
    gemini_price_pro_input: float = 1.25
    gemini_price_pro_output: float = 10.0
    gemini_price_flash_input: float = 0.30
    gemini_price_flash_output: float = 2.50
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/adapters/usage.py backend/src/explorator/config.py backend/tests/unit/adapters/test_usage.py
git commit -m "feat(usage): context-scoped Gemini token accumulator + pricing"
```

---

## Task 2: Capture usage in the Gemini adapter

**Files:**
- Modify: `backend/src/explorator/adapters/gemini.py:62-68` and `:144-150`
- Test: `backend/tests/unit/adapters/test_usage.py` (append)

- [ ] **Step 1: Write the failing test (append to test_usage.py)**

```python
async def test_adapter_records_usage_within_scope() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from pydantic import BaseModel

    from explorator.adapters.gemini import GeminiClient, ModelTier

    class _Sample(BaseModel):
        name: str
        value: int

    client = GeminiClient(api_key="test-key")
    fake_response = SimpleNamespace(
        text='{"name": "x", "value": 1}',
        usage_metadata=SimpleNamespace(
            prompt_token_count=120, candidates_token_count=30, cached_content_token_count=0
        ),
    )
    client._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            await client.generate_structured("p", _Sample, tier=ModelTier.PRO)

    assert u.totals() == {"input": 120, "output": 30, "cached": 0, "total": 150}
    assert u.by_phase["generate"].model == "pro"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py::test_adapter_records_usage_within_scope -v`
Expected: FAIL — `u.totals()` shows all zeros (adapter does not record yet).

- [ ] **Step 3: Add the import and two record calls**

In `backend/src/explorator/adapters/gemini.py`, add after line 9 (`from google.genai import types`):

```python
from explorator.adapters import usage
```

In `generate_structured`, immediately after the `generate_content` call (after line 66, the closing `)` of the call, before `raw_text = response.text`):

```python
        usage.record(model_name, response.usage_metadata)
```

In `generate_text`, immediately after its `generate_content` call (after line 148, before `if response.text is None:`):

```python
        usage.record(model_name, response.usage_metadata)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/adapters/gemini.py backend/tests/unit/adapters/test_usage.py
git commit -m "feat(usage): record usage_metadata in Gemini adapter calls"
```

---

## Task 3: Synthetic usage in the mock client

**Files:**
- Modify: `backend/src/explorator/adapters/gemini_mock.py:204-237`
- Test: `backend/tests/unit/adapters/test_usage.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
async def test_mock_client_records_synthetic_usage() -> None:
    from explorator.adapters.gemini import ModelTier
    from explorator.adapters.gemini_mock import FakeGeminiClient
    from explorator.domain.intent.parser import SoftPreferences  # noqa: F401  (registered builder)

    client = FakeGeminiClient()
    with usage.track_usage() as u:
        with usage.set_phase("parse_intent"):
            await client.generate_structured("p", SoftPreferences, tier=ModelTier.FLASH)
    assert u.totals()["total"] > 0
    assert u.by_phase["parse_intent"].calls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py::test_mock_client_records_synthetic_usage -v`
Expected: FAIL — totals total is 0 (mock records nothing).

- [ ] **Step 3: Record synthetic usage in the mock**

In `backend/src/explorator/adapters/gemini_mock.py`, add after line 17 (`from explorator.adapters.gemini import ModelTier`):

```python
from explorator.adapters import usage
```

In `generate_structured`, after `self.call_counts[name] += 1` (line 217), add:

```python
        usage.record_tokens(self.get_model_name(tier), 800, 200)
```

In `generate_text`, after `self.call_counts["generate_text"] += 1` (line 227), add:

```python
        usage.record_tokens(self.get_model_name(tier), 1200, 400)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/adapters/gemini_mock.py backend/tests/unit/adapters/test_usage.py
git commit -m "feat(usage): synthetic token usage in FakeGeminiClient"
```

---

## Task 4: Phase attribution + live emit in the graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Test: `backend/tests/unit/adapters/test_usage.py` (append — exercises the wrapper directly)

- [ ] **Step 1: Write the failing test (append)**

```python
async def test_instrument_sets_phase_and_emits_on_change() -> None:
    from explorator.engine.graph import _instrument

    emitted: list[tuple[str, dict]] = []

    async def on_progress(event_type: str, data: dict) -> None:
        emitted.append((event_type, data))

    async def fake_node(state: dict) -> dict:
        # Simulate an LLM call attributed to this node's phase.
        usage.record_tokens("gemini-pro-latest", 300, 100)
        return {}

    wrapped = _instrument("generate", fake_node)

    with usage.track_usage() as u:
        await wrapped({"on_progress": on_progress, "round_number": 1})

    assert u.by_phase["generate"].input == 300
    assert emitted and emitted[0][0] == "token_usage"
    assert emitted[0][1]["total_tokens"] == 400


async def test_instrument_skips_emit_when_unchanged() -> None:
    from explorator.engine.graph import _instrument

    emitted: list[tuple[str, dict]] = []

    async def on_progress(event_type: str, data: dict) -> None:
        emitted.append((event_type, data))

    async def deterministic_node(state: dict) -> dict:
        return {}  # no token usage

    wrapped = _instrument("assemble", deterministic_node)
    with usage.track_usage():
        await wrapped({"on_progress": on_progress, "round_number": 1})

    assert emitted == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -k instrument -v`
Expected: FAIL — `ImportError: cannot import name '_instrument'`.

- [ ] **Step 3: Add the wrapper and apply it at every node registration**

In `backend/src/explorator/engine/graph.py`, add to the imports (after line 14, `from neo4j import AsyncDriver`):

```python
import contextlib
from collections.abc import Awaitable, Callable

from explorator.adapters.usage import current_usage, set_phase
```

Add this helper above `_add_m2_nodes` (after line 38):

```python
def _instrument(
    name: str, fn: Callable[[ExplorationState], Awaitable[dict[str, Any]]]
) -> Callable[[ExplorationState], Awaitable[dict[str, Any]]]:
    """Wrap a node to (a) attribute token usage to its phase and (b) emit a live
    ``token_usage`` SSE event when the round's cumulative tokens grew.

    Emit is best-effort and guarded: a failing/absent callback never breaks the
    graph. Deterministic nodes that spend no tokens emit nothing (no duplicate
    events) because ``changed_since_last_emit()`` gates the send.
    """

    async def wrapped(state: ExplorationState) -> dict[str, Any]:
        with set_phase(name):
            result = await fn(state)
        callback = state.get("on_progress")
        accumulator = current_usage()
        if callback is not None and accumulator is not None and accumulator.changed_since_last_emit():
            round_number = state.get("round_number", 1)
            with contextlib.suppress(Exception):
                await callback("token_usage", accumulator.to_event(round_number))
        return result

    return wrapped
```

Then wrap every `graph.add_node(...)` call so the registered function is instrumented. Replace the body of `_add_m2_nodes` (lines 46-54) with:

```python
    graph.add_node("load_context", _instrument("load_context", partial(load_context, driver=driver)))
    graph.add_node("plan_voicings", _instrument("plan_voicings", partial(plan_voicings, gemini=gemini)))
    graph.add_node("generate_bass", _instrument("generate_bass", generate_bass))
    graph.add_node("generate_groove", _instrument("generate_groove", generate_groove))
    graph.add_node("generate_melody", _instrument("generate_melody", partial(generate_melody, gemini=gemini)))
    graph.add_node("assemble", _instrument("assemble", assemble_arrangements))
    graph.add_node("evaluate_arrangements", _instrument("evaluate_arrangements", evaluate_arrangements))
    graph.add_node("rank_and_select", _instrument("rank_and_select", rank_and_select))
    graph.add_node("persist_realization", _instrument("persist_realization", partial(persist_realization, driver=driver)))
```

In `build_exploration_graph`, replace the node registrations (lines 92-99, 108, 111, 124-125) with the instrumented forms:

```python
    # M1 nodes
    graph.add_node("parse_intent", _instrument("parse_intent", partial(parse_intent, gemini=gemini)))
    graph.add_node("load_genre", _instrument("load_genre", partial(load_genre, driver=driver)))
    graph.add_node("generate", _instrument("generate", partial(generate, gemini=gemini)))
    graph.add_node("evaluate_progressions", _instrument("evaluate_progressions", partial(evaluate_progressions, gemini=gemini)))
    graph.add_node("select_top_progressions", _instrument("select_top_progressions", select_top_progressions))

    # M3b: memory/feedback node
    graph.add_node("load_memory", _instrument("load_memory", partial(load_memory, driver=driver)))
```

```python
    graph.add_node("harvest_patterns", _instrument("harvest_patterns", partial(harvest_patterns, repo=pattern_repo)))
```

```python
    graph.add_node("persist_round", _instrument("persist_round", partial(persist_round, driver=driver)))
```

```python
    # M3a: mutation loop
    graph.add_node("check_stop", _instrument("check_stop", check_stop))
    graph.add_node("mutate", _instrument("mutate", partial(mutate, gemini=gemini)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/adapters/test_usage.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Run the engine graph test suite to confirm no regression**

Run: `cd backend && uv run pytest tests/ -k "graph or round" -q`
Expected: PASS (existing graph/round tests still green).

- [ ] **Step 6: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/unit/adapters/test_usage.py
git commit -m "feat(usage): per-phase attribution + live token_usage emit in graph"
```

---

## Task 5: Scope + terminal event in the round routes

**Files:**
- Modify: `backend/src/explorator/api/routes/rounds.py:117-124`
- Modify: `backend/src/explorator/api/routes/genre_research.py:124-133`
- Test: `backend/tests/api/test_token_usage_event.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_token_usage_event.py
"""The round route emits a terminal token_usage SSE event."""

import json


def _sse_events(resp) -> list[tuple[str, dict]]:
    """Parse an SSE response body into (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    for raw in resp.iter_lines():
        line = raw if isinstance(raw, str) else raw.decode()
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event_name:
            events.append((event_name, json.loads(line.split(":", 1)[1].strip())))
            event_name = None
    return events


def test_round_emits_terminal_token_usage(client_memory, monkeypatch):
    """A round whose graph spends tokens (within the scope) emits token_usage."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds
    from explorator.adapters import usage

    async def fake_ainvoke(state, *_a, **_k):
        # Simulate an in-scope LLM call (the route opened track_usage around us).
        usage.record_tokens("gemini-pro-latest", 1000, 400)
        return {}

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "dreamy"}
    ).json()["session_id"]

    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={}
    ) as resp:
        assert resp.status_code == 200
        events = _sse_events(resp)

    token_events = [data for name, data in events if name == "token_usage"]
    assert token_events, "expected a token_usage event"
    final = token_events[-1]
    assert final["total_tokens"] == 1400
    assert final["by_model"]["pro"]["calls"] == 1
    assert final["is_estimate"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_token_usage_event.py -v`
Expected: FAIL — no `token_usage` event (route doesn't open a scope or emit).

- [ ] **Step 3: Wrap the round graph run and emit the terminal event**

In `backend/src/explorator/api/routes/rounds.py`, add to imports (after line 14, `from explorator.api.sse import ...`):

```python
from explorator.adapters.usage import track_usage
```

Replace `run_and_close` (lines 117-124) with:

```python
    async def run_and_close() -> None:
        try:
            with track_usage() as round_usage:
                await graph.ainvoke(initial_state, {"recursion_limit": 100})
                await channel.send(
                    "token_usage", round_usage.to_event(initial_state.get("round_number", 1))
                )
        except Exception as e:
            logger.exception("Round failed for session %s", session_id)
            await channel.send("round_error", {"error": str(e)})
        finally:
            await channel.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_token_usage_event.py -v`
Expected: PASS

- [ ] **Step 5: Apply the same scope to genre research**

In `backend/src/explorator/api/routes/genre_research.py`, add to imports (after line 17, `from explorator.api.sse import SSEChannel`):

```python
from explorator.adapters.usage import track_usage
```

Replace `run_and_close` (lines 124-133) with:

```python
    async def run_and_close() -> None:
        try:
            with track_usage() as job_usage:
                await graph.ainvoke(initial_state, {"recursion_limit": 20})
                await channel.send("token_usage", job_usage.to_event(1))
        except Exception as e:
            logger.exception("Genre research failed for job %s", job_id)
            await repo.update_job(job_id, {"status": "failed", "error_message": str(e)})
            await channel.send("genre_research", {"status": "failed", "detail": str(e)})
        finally:
            await channel.close()
            _channels.pop(job_id, None)
```

- [ ] **Step 6: Run the API suite to confirm no regression**

Run: `cd backend && uv run pytest tests/api/ -q`
Expected: PASS (all API tests green, including the new one).

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/api/routes/rounds.py backend/src/explorator/api/routes/genre_research.py backend/tests/api/test_token_usage_event.py
git commit -m "feat(usage): open usage scope + emit terminal token_usage in routes"
```

---

## Task 6: Frontend SSE type + TokenUsage interface

**Files:**
- Modify: `frontend/src/services/sse.ts:1-10`

- [ ] **Step 1: Add `token_usage` to the event union and export the type**

In `frontend/src/services/sse.ts`, replace the union (lines 1-10) with:

```typescript
export type SSEEventType =
  | 'node_started'
  | 'node_completed'
  | 'candidates_preview'
  | 'round_completed'
  | 'round_error'
  | 'mutation_completed'
  | 'mutation_error'
  | 'realization_completed'
  | 'realization_error'
  | 'token_usage';

export interface TokenUsageBreakdown {
  input: number;
  output: number;
  calls: number;
}

export interface TokenUsage {
  round: number;
  total_input: number;
  total_output: number;
  total_cached: number;
  total_tokens: number;
  by_model: Record<string, { input: number; output: number; cached: number; calls: number }>;
  by_phase: Record<string, TokenUsageBreakdown & { model: string }>;
  estimated_cost_usd: number;
  is_estimate: boolean;
}
```

- [ ] **Step 2: Verify the frontend still type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/sse.ts
git commit -m "feat(usage): add token_usage SSE event type + TokenUsage interface"
```

---

## Task 7: Token usage in the candidate store

**Files:**
- Modify: `frontend/src/stores/candidateStore.ts`
- Test: `frontend/src/stores/__tests__/tokenUsageStore.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/stores/__tests__/tokenUsageStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useCandidateStore, sessionTokenTotals } from '../candidateStore';
import type { TokenUsage } from '../../services/sse';

function usage(round: number, total: number): TokenUsage {
  return {
    round,
    total_input: total,
    total_output: 0,
    total_cached: 0,
    total_tokens: total,
    by_model: { pro: { input: total, output: 0, cached: 0, calls: 1 } },
    by_phase: { generate: { input: total, output: 0, calls: 1, model: 'pro' } },
    estimated_cost_usd: total / 1000,
    is_estimate: true,
  };
}

describe('candidateStore token usage', () => {
  beforeEach(() => useCandidateStore.getState().reset());

  it('setLiveUsage exposes the in-flight running total', () => {
    useCandidateStore.getState().setLiveUsage(usage(1, 500));
    expect(useCandidateStore.getState().live?.total_tokens).toBe(500);
  });

  it('commitLiveUsage moves live into history and clears live', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();
    expect(useCandidateStore.getState().live).toBeNull();
    expect(useCandidateStore.getState().usages).toHaveLength(1);
  });

  it('sessionTokenTotals sums history plus any in-flight live (no double count)', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();                       // history: [500]
    s.setLiveUsage(usage(1, 300));             // live: 300, not yet committed
    const totals = sessionTokenTotals(useCandidateStore.getState());
    expect(totals.tokens).toBe(800);
    expect(totals.cost).toBeCloseTo(0.8, 5);
  });

  it('reset clears usage state', () => {
    const s = useCandidateStore.getState();
    s.setLiveUsage(usage(1, 500));
    s.commitLiveUsage();
    s.reset();
    expect(useCandidateStore.getState().usages).toHaveLength(0);
    expect(useCandidateStore.getState().live).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/stores/__tests__/tokenUsageStore.test.ts`
Expected: FAIL — `setLiveUsage`/`sessionTokenTotals` are not exported.

- [ ] **Step 3: Extend the store**

In `frontend/src/stores/candidateStore.ts`, change the import line (line 2) to also import `TokenUsage`:

```typescript
import type { CandidateSummary, FinalSelection } from '../services/api';
import type { TokenUsage } from '../services/sse';
```

Add to the `CandidateState` interface (after `selectedForComparison: string[];`, line 10):

```typescript
  usages: TokenUsage[];
  live: TokenUsage | null;
  setLiveUsage: (u: TokenUsage) => void;
  commitLiveUsage: () => void;
```

Add to the store initial state + actions (inside `create`, after `selectedForComparison: [],` on line 29):

```typescript
  usages: [],
  live: null,
  setLiveUsage: (live) => set({ live }),
  commitLiveUsage: () =>
    set((state) => (state.live ? { usages: [...state.usages, state.live], live: null } : {})),
```

Update `reset` (lines 45-53) to also clear usage state by adding these two lines inside the `set({...})`:

```typescript
      usages: [],
      live: null,
```

Add this selector helper at the end of the file (after the closing `}));`):

```typescript
export function sessionTokenTotals(state: CandidateState): { tokens: number; cost: number } {
  const committed = state.usages;
  const all = state.live ? [...committed, state.live] : committed;
  return {
    tokens: all.reduce((sum, u) => sum + u.total_tokens, 0),
    cost: all.reduce((sum, u) => sum + u.estimated_cost_usd, 0),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/stores/__tests__/tokenUsageStore.test.ts`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/candidateStore.ts frontend/src/stores/__tests__/tokenUsageStore.test.ts
git commit -m "feat(usage): track live + committed token usage in candidate store"
```

---

## Task 8: Consume `token_usage` in the generation flow

**Files:**
- Modify: `frontend/src/hooks/useGenerationFlow.ts`
- Test: `frontend/src/hooks/__tests__/useGenerationFlow.tokenUsage.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/hooks/__tests__/useGenerationFlow.tokenUsage.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGenerationFlow } from '../useGenerationFlow';
import { useCandidateStore } from '../../stores/candidateStore';

// Hoisted: stub the post-stream candidate reload so it doesn't hit the network.
vi.mock('../../services/api', () => ({
  listCandidates: vi.fn(() => Promise.resolve({ items: [] })),
}));

// A real fetch-style Response whose body streams one SSE token_usage event,
// then a round_completed, then closes.
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
      } else {
        controller.close();
      }
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

describe('useGenerationFlow — token_usage', () => {
  beforeEach(() => {
    useCandidateStore.getState().reset();
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(
        sseResponse([
          'event: token_usage\ndata: {"round":1,"total_input":1000,"total_output":400,"total_cached":0,"total_tokens":1400,"by_model":{"pro":{"input":1000,"output":400,"cached":0,"calls":1}},"by_phase":{"generate":{"input":1000,"output":400,"calls":1,"model":"pro"}},"estimated_cost_usd":0.005,"is_estimate":true}\n\n',
          'event: round_completed\ndata: {"round":1}\n\n',
        ]),
      ),
    ));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('stores live usage from a token_usage event and commits on completion', async () => {
    const { result } = renderHook(() => useGenerationFlow('session-1'));
    await act(async () => {
      await result.current.generate('a dreamy progression');
    });
    // After a successful round, the live snapshot is committed into history.
    expect(useCandidateStore.getState().usages).toHaveLength(1);
    expect(useCandidateStore.getState().usages[0].total_tokens).toBe(1400);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useGenerationFlow.tokenUsage.test.ts`
Expected: FAIL — `usages` is empty (hook ignores `token_usage`).

- [ ] **Step 3: Handle the event in the hook**

In `frontend/src/hooks/useGenerationFlow.ts`, add a `TokenUsage` import after line 6 (`import { streamSSE, ... } from './streamSSE';`):

```typescript
import type { TokenUsage } from '../services/sse';
```

Change the store destructure (line 24) to:

```typescript
  const { setCandidates, setFinalSelection, setLiveUsage, commitLiveUsage } = useCandidateStore();
```

Add a handler branch in `onEvent`, immediately after the `node_started` branch (after line 86, before `} else if (eventType === 'round_completed')`):

```typescript
          } else if (eventType === 'token_usage') {
            setLiveUsage(data as unknown as TokenUsage);
```

In the success path, after the candidate reload succeeds — inside `if (!streamFailed) {` after `if (mountedRef.current) setCandidates(res.items);` (line 123) — add:

```typescript
          commitLiveUsage();
```

Update the `useCallback` dependency array (line 149) to include the new actions:

```typescript
  }, [sessionId, loading, setCandidates, setFinalSelection, setLiveUsage, commitLiveUsage]);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useGenerationFlow.tokenUsage.test.ts`
Expected: PASS

- [ ] **Step 5: Run the existing hook test to confirm no regression**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useGenerationFlow.test.ts`
Expected: PASS (unchanged behavior).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useGenerationFlow.ts frontend/src/hooks/__tests__/useGenerationFlow.tokenUsage.test.ts
git commit -m "feat(usage): consume token_usage events in generation flow"
```

---

## Task 9: TokenUsagePanel component

**Files:**
- Create: `frontend/src/components/TokenUsagePanel.tsx`
- Test: `frontend/src/components/__tests__/TokenUsagePanel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/__tests__/TokenUsagePanel.test.tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import TokenUsagePanel from '../TokenUsagePanel';
import { useCandidateStore } from '../../stores/candidateStore';
import type { TokenUsage } from '../../services/sse';

const sample: TokenUsage = {
  round: 1,
  total_input: 1000,
  total_output: 400,
  total_cached: 0,
  total_tokens: 1400,
  by_model: { pro: { input: 1000, output: 400, cached: 0, calls: 1 } },
  by_phase: { generate: { input: 1000, output: 400, calls: 1, model: 'pro' } },
  estimated_cost_usd: 0.005,
  is_estimate: true,
};

describe('TokenUsagePanel', () => {
  beforeEach(() => useCandidateStore.getState().reset());

  it('renders nothing when there is no usage', () => {
    const { container } = render(<TokenUsagePanel />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the round total tokens and an estimated cost', () => {
    useCandidateStore.getState().setLiveUsage(sample);
    render(<TokenUsagePanel />);
    expect(screen.getByTestId('token-usage-panel')).toBeInTheDocument();
    expect(screen.getByText(/1,400/)).toBeInTheDocument();
    expect(screen.getByText(/est\./)).toBeInTheDocument();
  });

  it('lists the per-phase breakdown', () => {
    useCandidateStore.getState().setLiveUsage(sample);
    render(<TokenUsagePanel />);
    expect(screen.getByText(/generate/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/TokenUsagePanel.test.tsx`
Expected: FAIL — cannot resolve `../TokenUsagePanel`.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/TokenUsagePanel.tsx
import { useCandidateStore, sessionTokenTotals } from '../stores/candidateStore';

const fmt = (n: number) => n.toLocaleString('en-US');
const usd = (n: number) => `~$${n < 0.01 ? n.toFixed(4) : n.toFixed(3)} est.`;

export default function TokenUsagePanel() {
  const live = useCandidateStore((s) => s.live);
  const usages = useCandidateStore((s) => s.usages);
  const current = live ?? (usages.length ? usages[usages.length - 1] : null);
  const session = sessionTokenTotals(useCandidateStore.getState());

  if (!current) return null;

  const phases = Object.entries(current.by_phase).sort(
    (a, b) => b[1].input + b[1].output - (a[1].input + a[1].output),
  );

  return (
    <div
      data-testid="token-usage-panel"
      className="rounded-lg px-4 py-3 text-xs"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border-subtle)' }}
    >
      <div className="flex items-center justify-between">
        <span className="uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
          Token usage
        </span>
        <span className="font-mono" style={{ color: 'var(--text-primary)' }}>
          {fmt(current.total_tokens)} tokens
          <span style={{ color: 'var(--text-muted)' }}>
            {' '}({fmt(current.total_input)} in / {fmt(current.total_output)} out)
          </span>
          <span className="ml-2" style={{ color: 'var(--accent-primary)' }}>{usd(current.estimated_cost_usd)}</span>
        </span>
      </div>

      <details className="mt-2">
        <summary className="cursor-pointer" style={{ color: 'var(--text-muted)' }}>
          Breakdown by step
        </summary>
        <div className="mt-2 flex flex-col gap-1">
          {phases.map(([name, p]) => (
            <div key={name} className="flex items-center justify-between font-mono">
              <span style={{ color: 'var(--text-secondary)' }}>
                {name} <span style={{ color: 'var(--text-muted)' }}>({p.model})</span>
              </span>
              <span style={{ color: 'var(--text-muted)' }}>
                {fmt(p.input + p.output)} tokens · {p.calls} call{p.calls === 1 ? '' : 's'}
              </span>
            </div>
          ))}
        </div>
      </details>

      <div className="mt-2 pt-2 flex items-center justify-between" style={{ borderTop: '1px solid var(--border-subtle)' }}>
        <span style={{ color: 'var(--text-muted)' }}>This session</span>
        <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
          {fmt(session.tokens)} tokens · {usd(session.cost)}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/TokenUsagePanel.test.tsx`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TokenUsagePanel.tsx frontend/src/components/__tests__/TokenUsagePanel.test.tsx
git commit -m "feat(usage): TokenUsagePanel with round/phase/session breakdown"
```

---

## Task 10: Render the panel in the workspace

**Files:**
- Modify: `frontend/src/views/SessionWorkspace.tsx:11-22, 238-240`

- [ ] **Step 1: Add the import**

In `frontend/src/views/SessionWorkspace.tsx`, add after line 11 (`import PromptBar from '../components/PromptBar';`):

```typescript
import TokenUsagePanel from '../components/TokenUsagePanel';
```

- [ ] **Step 2: Render the panel below the prompt bar**

Immediately after the closing `</div>` of the prompt-bar section (after line 238, before the `{/* Error */}` comment), add:

```tsx
      {/* Token usage */}
      <TokenUsagePanel />
```

- [ ] **Step 3: Verify type-check + full frontend test run**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS (type-check clean; all suites green).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/SessionWorkspace.tsx
git commit -m "feat(usage): surface TokenUsagePanel in the session workspace"
```

---

## Task 11: Full verification + manual check

- [ ] **Step 1: Backend suite**

Run: `cd backend && uv run pytest tests/unit tests/api -q`
Expected: PASS (all green).

- [ ] **Step 2: Backend lint**

Run: `cd backend && uv run ruff check src/explorator/adapters/usage.py src/explorator/engine/graph.py src/explorator/api/routes/rounds.py`
Expected: PASS (no lint errors).

- [ ] **Step 3: Frontend suite + type-check**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: PASS.

- [ ] **Step 4: Manual smoke (mock mode — no API spend)**

Run backend with `GEMINI_MOCK=true` and the frontend dev server, create a session, generate a round, and confirm:
- The TokenUsagePanel appears under the prompt bar.
- Token counts tick up live as phases complete, then settle on a final total.
- "Breakdown by step" lists phases (e.g. `generate (pro)`, `evaluate_progressions (flash)`).
- "This session" total grows after a second generate.

- [ ] **Step 5: Manual smoke (real Gemini — optional)**

With a real `GEMINI_API_KEY` (copy `backend/.env` per project memory), run one round and confirm the per-model split and counts look plausible against the number of LLM calls.

- [ ] **Step 6: Update the todo review section**

Append a short "Review" summary to `tasks/todo.md` (what shipped, any deviations) and commit:

```bash
git add tasks/todo.md
git commit -m "docs: token usage instrumentation review notes"
```

---

## Self-Review

**Spec coverage:**
- Per-round cost awareness → Tasks 1, 5, 9 (headline tokens + cost). ✓
- Understand the distribution (by phase) → Tasks 1 (`by_phase`), 4 (attribution), 9 (breakdown UI). ✓
- Session-cumulative total → Tasks 7 (`sessionTokenTotals`), 9 (footer). ✓
- Live during a round → Tasks 4 (live emit), 8 (consume), 9 (display). ✓
- Cost as labeled estimate + configurable rates → Task 1 (config + `is_estimate`), 9 (`~$… est.`). ✓
- Genre research total → Task 5. ✓
- Mock exercises UI → Task 3. ✓
- Non-goal (no Neo4j persistence) → respected; cumulative is frontend-only. ✓

**Type consistency:** `TokenUsage` (sse.ts) ↔ `to_event` keys (usage.py) match field-for-field: `round, total_input, total_output, total_cached, total_tokens, by_model, by_phase, estimated_cost_usd, is_estimate`. Store actions `setLiveUsage`/`commitLiveUsage` and selector `sessionTokenTotals` are used identically in Tasks 7/8/9. Backend `record_tokens`/`record`/`track_usage`/`set_phase`/`current_usage`/`_instrument` names are consistent across Tasks 1–5.

**Placeholder scan:** none — every step has concrete code and exact commands.
