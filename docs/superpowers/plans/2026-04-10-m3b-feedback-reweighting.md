# M3b — Feedback & Reweighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to submit natural-language feedback on candidates, have Gemini Flash interpret it into objective weight adjustments, and re-rank candidates with the adjusted weights.

**Architecture:** Feedback enters via a new REST endpoint, is interpreted by a `FeedbackInterpreter` domain service (Gemini Flash), produces weight deltas that are clamped/renormalized into a new `ObjectiveWeights` profile, and persisted as a `UserFeedbackEvent` in Neo4j. A new `load_memory` graph node injects feedback history and current weights into state before generation. `rank_and_select` reads weights from state instead of its hardcoded dict. `check_stop` gains a 4th stop condition (user satisfaction). Frontend adds a chat-style feedback sidebar with weight visualization.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Neo4j (async), Gemini Flash, Pydantic v2, React 18, Zustand, Tailwind CSS

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/src/explorator/domain/intent/feedback.py` | `FeedbackInterpreter` service — Gemini Flash interprets feedback text → weight deltas |
| Create | `backend/src/explorator/prompts/feedback.py` | Prompt builder for feedback interpretation |
| Create | `backend/src/explorator/engine/nodes/load_memory.py` | `load_memory` node — loads feedback history + objective weights from Neo4j |
| Create | `backend/src/explorator/graph/feedback_repo.py` | `FeedbackEventRepo` + `ObjectiveWeightsRepo` for Neo4j persistence |
| Create | `backend/src/explorator/api/routes/feedback.py` | `POST /v1/sessions/{session_id}/feedback` endpoint |
| Modify | `backend/src/explorator/engine/state.py:10-63` | Add `feedback_history`, `objective_weights`, `user_preference_profile` fields |
| Modify | `backend/src/explorator/models/memory.py:22-29` | Add `weight_deltas` field to `UserFeedbackEvent` |
| Modify | `backend/src/explorator/engine/nodes/rank_and_select.py:15,194,234` | Read weights from `state["objective_weights"]` instead of hardcoded `DEFAULT_WEIGHTS` |
| Modify | `backend/src/explorator/engine/nodes/check_stop.py:11-56` | Add stop condition 4: user satisfaction |
| Modify | `backend/src/explorator/engine/graph.py` | Insert `load_memory` node after `load_genre`, before `generate` |
| Modify | `backend/src/explorator/api/app.py:10-60` | Register feedback router |
| Create | `backend/tests/unit/prompts/test_feedback_prompt.py` | Tests for prompt builder |
| Create | `backend/tests/unit/domain/test_feedback_interpreter.py` | Tests for FeedbackInterpreter |
| Create | `backend/tests/unit/engine/test_load_memory.py` | Tests for load_memory node |
| Modify | `backend/tests/unit/engine/test_check_stop.py` | Add satisfaction stop tests |
| Modify | `backend/tests/unit/engine/test_rank_and_select.py` | Test state-driven weights |
| Create | `frontend/src/stores/feedbackStore.ts` | Zustand store for feedback history + current weights |
| Create | `frontend/src/components/FeedbackSidebar.tsx` | Chat-style sidebar with weight bars |
| Modify | `frontend/src/services/api.ts` | Add `submitFeedback()` API call |
| Modify | `frontend/src/services/sse.ts` | Add `feedback_processed` event type |
| Modify | `frontend/src/views/SessionWorkspace.tsx` | Integrate FeedbackSidebar in realization view |

---

### Task 1: State Additions

**Files:**
- Modify: `backend/src/explorator/engine/state.py:10-63`
- Test: `backend/tests/unit/engine/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/engine/test_state.py — append to existing file

def test_feedback_fields_in_state() -> None:
    """M3b state fields are valid keys."""
    from explorator.engine.state import ExplorationState

    state: ExplorationState = {
        "feedback_history": [{"id": "fb_1", "content": "too busy"}],
        "objective_weights": {"genre_fit": 0.15, "novelty": 0.10},
        "user_preference_profile": {},
    }
    assert state["feedback_history"][0]["content"] == "too busy"
    assert state["objective_weights"]["genre_fit"] == 0.15
    assert state["user_preference_profile"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_state.py::test_feedback_fields_in_state -v`
Expected: FAIL — `feedback_history` is not a valid key for ExplorationState

- [ ] **Step 3: Add fields to ExplorationState**

Add to `backend/src/explorator/engine/state.py`, after the M3a block (line 57):

```python
    # --- M3b: Feedback & Memory ---
    feedback_history: list[dict[str, Any]]
    objective_weights: dict[str, Any]
    user_preference_profile: dict[str, Any]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/engine/state.py backend/tests/unit/engine/test_state.py && git commit -m "feat(m3b): add feedback_history, objective_weights, user_preference_profile to ExplorationState"
```

---

### Task 2: Extend UserFeedbackEvent Model

**Files:**
- Modify: `backend/src/explorator/models/memory.py:22-29`
- Modify: `backend/tests/unit/models/test_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/models/test_memory.py — append

def test_user_feedback_event_has_weight_deltas() -> None:
    from explorator.models.memory import UserFeedbackEvent

    fb = UserFeedbackEvent(
        id="fb_1",
        type="user_feedback_event",
        status="active",
        session_id="sess_1",
        candidate_id="arr_1",
        content="bass is too busy",
        interpreted_adjustments={"reduce_bass_motion": True},
        weight_deltas={"playability": 0.04, "voice_leading": -0.02, "novelty": -0.02},
    )
    assert fb.weight_deltas["playability"] == 0.04
    assert fb.feedback_type == "text_reaction"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/models/test_memory.py::test_user_feedback_event_has_weight_deltas -v`
Expected: FAIL — `weight_deltas` unexpected keyword argument

- [ ] **Step 3: Add weight_deltas field**

In `backend/src/explorator/models/memory.py`, add to `UserFeedbackEvent`:

```python
class UserFeedbackEvent(BaseEntity):
    """Explicit user reaction."""

    session_id: str
    candidate_id: str
    feedback_type: str = "text_reaction"
    content: str = ""
    interpreted_adjustments: dict[str, Any] = Field(default_factory=dict)
    weight_deltas: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/models/test_memory.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/models/memory.py backend/tests/unit/models/test_memory.py && git commit -m "feat(m3b): add weight_deltas field to UserFeedbackEvent"
```

---

### Task 3: Feedback Interpretation Prompt

**Files:**
- Create: `backend/src/explorator/prompts/feedback.py`
- Create: `backend/tests/unit/prompts/test_feedback_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/prompts/test_feedback_prompt.py

from explorator.prompts.feedback import feedback_interpretation_prompt

WEIGHT_DIMENSIONS = [
    "genre_fit", "emotional_fit", "theoretical_coherence",
    "cadence_quality", "novelty", "loopability",
    "voice_leading", "register_density", "playability",
]


def test_prompt_includes_feedback_text() -> None:
    user_prompt, system_prompt = feedback_interpretation_prompt(
        feedback_text="bass is too busy, prefer open voicings",
        current_weights={"genre_fit": 0.15, "novelty": 0.10},
        candidate_scores={"genre_fit": 7.0, "novelty": 6.5},
        genre="dream_pop",
    )
    assert "bass is too busy" in user_prompt
    assert "dream_pop" in user_prompt
    assert system_prompt  # non-empty


def test_prompt_includes_current_weights() -> None:
    user_prompt, _ = feedback_interpretation_prompt(
        feedback_text="more experimental",
        current_weights={"novelty": 0.10, "genre_fit": 0.15},
        candidate_scores={},
        genre="lo_fi_hip_hop",
    )
    assert "novelty" in user_prompt
    assert "0.10" in user_prompt or "0.1" in user_prompt


def test_prompt_lists_all_weight_dimensions() -> None:
    user_prompt, _ = feedback_interpretation_prompt(
        feedback_text="test",
        current_weights={dim: round(1.0 / 9, 3) for dim in WEIGHT_DIMENSIONS},
        candidate_scores={},
        genre="jazz",
    )
    for dim in WEIGHT_DIMENSIONS:
        assert dim in user_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/prompts/test_feedback_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'explorator.prompts.feedback'`

- [ ] **Step 3: Implement the prompt builder**

```python
# backend/src/explorator/prompts/feedback.py
"""Feedback interpretation prompt for Gemini Flash."""

from __future__ import annotations

WEIGHT_DIMENSIONS = [
    "genre_fit", "emotional_fit", "theoretical_coherence",
    "cadence_quality", "novelty", "loopability",
    "voice_leading", "register_density", "playability",
]

DIMENSION_DESCRIPTIONS = {
    "genre_fit": "How well the progression fits the target genre conventions",
    "emotional_fit": "Alignment with the requested emotional tone/mood",
    "theoretical_coherence": "Harmonic theory correctness (voice leading rules, functional harmony)",
    "cadence_quality": "Strength and appropriateness of cadence points",
    "novelty": "Creative originality and surprise factor",
    "loopability": "How smoothly the progression can loop/repeat",
    "voice_leading": "Smoothness of individual voice movement between chords",
    "register_density": "Balance of note density across pitch registers",
    "playability": "Physical playability on keyboard/guitar",
}


def feedback_interpretation_prompt(
    feedback_text: str,
    current_weights: dict[str, float],
    candidate_scores: dict[str, float],
    genre: str,
) -> tuple[str, str]:
    """Build (user_prompt, system_prompt) for feedback interpretation.

    Returns a tuple of (user_prompt, system_prompt) strings suitable for
    passing to GeminiClient.generate_structured.
    """
    weights_str = "\n".join(
        f"  - {dim}: {current_weights.get(dim, 0.0):.3f} — {DIMENSION_DESCRIPTIONS.get(dim, '')}"
        for dim in WEIGHT_DIMENSIONS
    )

    scores_str = ", ".join(
        f"{k}={v:.1f}" for k, v in candidate_scores.items()
    ) if candidate_scores else "none available"

    user_prompt = f"""User feedback: "{feedback_text}"

Genre: {genre}
Candidate scores: {scores_str}

Current objective weights (9 dimensions, sum to 1.0):
{weights_str}

Based on the user's feedback:
1. Identify what the user wants changed (interpreted_adjustments).
2. Propose weight_deltas: adjustments to the 9 weight dimensions that reflect the user's preference. Deltas should be small (typically +-0.01 to +-0.05). They must sum to approximately 0.0 (zero-sum) so the total remains ~1.0 after application.
3. Determine if the user is expressing satisfaction with the current result (satisfaction field).

Return interpreted_adjustments (semantic map), weight_deltas (numerical), and satisfaction ("positive", "neutral", or "negative")."""

    system_prompt = (
        "You are a music production assistant interpreting user feedback on chord progressions "
        "and arrangements. Translate natural-language preferences into precise scoring weight "
        "adjustments. Be conservative with deltas — small shifts (0.01–0.05) are preferred. "
        "Only mark satisfaction as 'positive' if the user clearly expresses approval "
        '("love this", "perfect", "this is great"). Default to "neutral".'
    )

    return user_prompt, system_prompt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/prompts/test_feedback_prompt.py -v`
Expected: ALL PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/prompts/feedback.py backend/tests/unit/prompts/test_feedback_prompt.py && git commit -m "feat(m3b): feedback interpretation prompt builder"
```

---

### Task 4: FeedbackInterpreter Domain Service

**Files:**
- Create: `backend/src/explorator/domain/intent/feedback.py`
- Create: `backend/tests/unit/domain/test_feedback_interpreter.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/domain/test_feedback_interpreter.py
"""Tests for FeedbackInterpreter domain service."""

import json
from unittest.mock import AsyncMock

import pytest

from explorator.domain.intent.feedback import (
    FeedbackInterpretation,
    FeedbackInterpreter,
    apply_weight_deltas,
)
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS


def test_feedback_interpretation_model() -> None:
    fi = FeedbackInterpretation(
        interpreted_adjustments={"reduce_bass_motion": True},
        weight_deltas={"playability": 0.04, "voice_leading": -0.02, "novelty": -0.02},
        satisfaction="neutral",
    )
    assert fi.satisfaction == "neutral"
    assert fi.weight_deltas["playability"] == 0.04


def test_apply_weight_deltas_basic() -> None:
    current = {"genre_fit": 0.50, "novelty": 0.50}
    deltas = {"genre_fit": 0.05, "novelty": -0.05}
    result = apply_weight_deltas(current, deltas)
    assert abs(result["genre_fit"] - 0.55) < 0.001
    assert abs(result["novelty"] - 0.45) < 0.001
    assert abs(sum(result.values()) - 1.0) < 0.01


def test_apply_weight_deltas_clamps_to_bounds() -> None:
    current = {"genre_fit": 0.03, "novelty": 0.97}
    deltas = {"genre_fit": -0.10, "novelty": 0.10}
    result = apply_weight_deltas(current, deltas)
    # genre_fit should clamp to 0.02, not go below
    assert result["genre_fit"] >= 0.02
    # novelty should clamp to 0.50, not exceed
    assert result["novelty"] <= 0.50
    assert abs(sum(result.values()) - 1.0) < 0.01


def test_apply_weight_deltas_renormalizes() -> None:
    current = {"a": 0.30, "b": 0.30, "c": 0.40}
    deltas = {"a": 0.10, "b": 0.10}  # non-zero-sum deltas
    result = apply_weight_deltas(current, deltas)
    assert abs(sum(result.values()) - 1.0) < 0.01


@pytest.mark.asyncio
async def test_interpret_returns_feedback_interpretation() -> None:
    mock_gemini = AsyncMock()
    mock_gemini.generate_structured.return_value = FeedbackInterpretation(
        interpreted_adjustments={"prefer_open_voicings": True},
        weight_deltas={"playability": 0.03, "voice_leading": -0.03},
        satisfaction="neutral",
    )
    interpreter = FeedbackInterpreter(mock_gemini)
    result = await interpreter.interpret(
        feedback_text="prefer open voicings",
        current_weights=CANONICAL_DEFAULT_WEIGHTS.weights,
        candidate_scores={"genre_fit": 7.0},
        genre="dream_pop",
    )
    assert result.interpreted_adjustments["prefer_open_voicings"] is True
    assert result.weight_deltas["playability"] == 0.03
    mock_gemini.generate_structured.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/domain/test_feedback_interpreter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Check if domain/intent directory exists**

Run: `ls /home/angel/Documents/code/Explorator/backend/src/explorator/domain/intent/ 2>/dev/null || echo "MISSING"`

If missing, create `__init__.py`:
Run: `mkdir -p /home/angel/Documents/code/Explorator/backend/src/explorator/domain/intent && touch /home/angel/Documents/code/Explorator/backend/src/explorator/domain/intent/__init__.py`

- [ ] **Step 4: Implement FeedbackInterpreter**

```python
# backend/src/explorator/domain/intent/feedback.py
"""Feedback interpretation — Gemini Flash translates user text to weight deltas."""

import logging

from pydantic import BaseModel, Field

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.prompts.feedback import feedback_interpretation_prompt

logger = logging.getLogger(__name__)

# Clamp bounds for any single weight dimension
_WEIGHT_MIN = 0.02
_WEIGHT_MAX = 0.50


class FeedbackInterpretation(BaseModel):
    """Gemini Flash structured response for feedback interpretation."""

    interpreted_adjustments: dict[str, object] = Field(default_factory=dict)
    weight_deltas: dict[str, float] = Field(default_factory=dict)
    satisfaction: str = "neutral"  # "positive" | "neutral" | "negative"


def apply_weight_deltas(
    current_weights: dict[str, float],
    deltas: dict[str, float],
) -> dict[str, float]:
    """Apply deltas, clamp to [0.02, 0.50], renormalize to sum 1.0."""
    result = dict(current_weights)
    for dim, delta in deltas.items():
        if dim in result:
            result[dim] = result[dim] + delta

    # Clamp
    for dim in result:
        result[dim] = max(_WEIGHT_MIN, min(_WEIGHT_MAX, result[dim]))

    # Renormalize to sum 1.0
    total = sum(result.values())
    if total > 0:
        for dim in result:
            result[dim] = round(result[dim] / total, 4)

    return result


class FeedbackInterpreter:
    """Interprets user feedback text into weight adjustments using Gemini Flash."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def interpret(
        self,
        feedback_text: str,
        current_weights: dict[str, float],
        candidate_scores: dict[str, float],
        genre: str,
    ) -> FeedbackInterpretation:
        """Interpret feedback text into weight deltas via Gemini Flash."""
        user_prompt, system_prompt = feedback_interpretation_prompt(
            feedback_text=feedback_text,
            current_weights=current_weights,
            candidate_scores=candidate_scores,
            genre=genre,
        )

        result = await self.gemini.generate_structured(
            prompt=user_prompt,
            response_model=FeedbackInterpretation,
            tier=ModelTier.FLASH,
            system_prompt=system_prompt,
        )

        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/domain/test_feedback_interpreter.py -v`
Expected: ALL PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/domain/intent/ backend/tests/unit/domain/test_feedback_interpreter.py && git commit -m "feat(m3b): FeedbackInterpreter service with apply_weight_deltas"
```

---

### Task 5: Neo4j Repos for Feedback & Weights

**Files:**
- Create: `backend/src/explorator/graph/feedback_repo.py`

- [ ] **Step 1: Implement the repos**

```python
# backend/src/explorator/graph/feedback_repo.py
"""Neo4j repositories for feedback events and objective weights."""

from typing import Any

from explorator.graph.repository import BaseRepository


class FeedbackEventRepo(BaseRepository):
    """CRUD for UserFeedbackEvent nodes."""

    label = "UserFeedbackEvent"

    async def list_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """List all feedback events for a session, ordered by creation time."""
        query = """
            MATCH (n:UserFeedbackEvent {session_id: $session_id})
            RETURN properties(n) AS props
            ORDER BY n.created_at ASC
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            records = await result.data()
            from explorator.graph.repository import _neo4j_deserialize
            return [_neo4j_deserialize(dict(r["props"])) for r in records]


class ObjectiveWeightsRepo(BaseRepository):
    """CRUD for ObjectiveWeights nodes."""

    label = "ObjectiveWeights"

    async def get_latest_for_session(self, session_id: str) -> dict[str, Any] | None:
        """Get the most recently created ObjectiveWeights for a session."""
        query = """
            MATCH (n:ObjectiveWeights)
            WHERE n.profile_name STARTS WITH $prefix
            RETURN properties(n) AS props
            ORDER BY n.created_at DESC
            LIMIT 1
        """
        async with self.driver.session() as session:
            result = await session.run(query, prefix=f"session_{session_id}")
            record = await result.single()
            if record is None:
                return None
            from explorator.graph.repository import _neo4j_deserialize
            return _neo4j_deserialize(dict(record["props"]))
```

- [ ] **Step 2: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/graph/feedback_repo.py && git commit -m "feat(m3b): FeedbackEventRepo and ObjectiveWeightsRepo"
```

---

### Task 6: load_memory Node

**Files:**
- Create: `backend/src/explorator/engine/nodes/load_memory.py`
- Create: `backend/tests/unit/engine/test_load_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/engine/test_load_memory.py
"""Tests for load_memory node."""

import pytest
from unittest.mock import AsyncMock, patch

from explorator.engine.nodes.load_memory import load_memory
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS


def _make_state(session_id: str = "sess_1") -> dict:
    return {"session_id": session_id}


@pytest.mark.asyncio
async def test_load_memory_returns_defaults_when_no_feedback() -> None:
    mock_driver = AsyncMock()

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(return_value=[])
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(return_value=None)

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert result["feedback_history"] == []
    assert result["objective_weights"] == CANONICAL_DEFAULT_WEIGHTS.weights
    assert result["user_preference_profile"] == {}


@pytest.mark.asyncio
async def test_load_memory_returns_existing_feedback() -> None:
    mock_driver = AsyncMock()
    feedback = [{"id": "fb_1", "content": "too dark"}]
    custom_weights = {"genre_fit": 0.20, "novelty": 0.15}

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(return_value=feedback)
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(
            return_value={"weights": custom_weights}
        )

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert len(result["feedback_history"]) == 1
    assert result["objective_weights"] == custom_weights


@pytest.mark.asyncio
async def test_load_memory_timeout_returns_defaults() -> None:
    """If Neo4j times out, return safe defaults."""
    mock_driver = AsyncMock()

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(
            side_effect=TimeoutError("Neo4j timeout")
        )
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(
            side_effect=TimeoutError("Neo4j timeout")
        )

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert result["feedback_history"] == []
    assert result["objective_weights"] == CANONICAL_DEFAULT_WEIGHTS.weights
    assert result["user_preference_profile"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_load_memory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement load_memory node**

```python
# backend/src/explorator/engine/nodes/load_memory.py
"""load_memory node — deterministic data fetch for feedback history and objective weights."""

import asyncio
import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
from explorator.engine.state import ExplorationState
from explorator.graph.feedback_repo import FeedbackEventRepo, ObjectiveWeightsRepo

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


async def load_memory(
    state: ExplorationState,
    *,
    driver: AsyncDriver,
) -> dict[str, Any]:
    """Load feedback history and objective weights from Neo4j.

    Deterministic — no Gemini call. Falls back to canonical defaults on timeout.
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_memory"})

    session_id = state.get("session_id", "")
    fb_repo = FeedbackEventRepo(driver)
    ow_repo = ObjectiveWeightsRepo(driver)

    feedback_history: list[dict[str, Any]] = []
    objective_weights: dict[str, float] = dict(CANONICAL_DEFAULT_WEIGHTS.weights)
    user_preference_profile: dict[str, Any] = {}

    try:
        feedback_history = await asyncio.wait_for(
            fb_repo.list_by_session(session_id),
            timeout=_TIMEOUT_SECONDS,
        )
    except (TimeoutError, Exception) as exc:
        logger.warning("load_memory: failed to load feedback history: %s", exc)

    try:
        latest_weights = await asyncio.wait_for(
            ow_repo.get_latest_for_session(session_id),
            timeout=_TIMEOUT_SECONDS,
        )
        if latest_weights and "weights" in latest_weights:
            objective_weights = latest_weights["weights"]
    except (TimeoutError, Exception) as exc:
        logger.warning("load_memory: failed to load objective weights: %s", exc)

    if callback:
        await callback("node_completed", {
            "node": "load_memory",
            "feedback_count": len(feedback_history),
            "weights_source": "session" if feedback_history else "canonical_default",
        })

    return {
        "feedback_history": feedback_history,
        "objective_weights": objective_weights,
        "user_preference_profile": user_preference_profile,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_load_memory.py -v`
Expected: ALL PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/engine/nodes/load_memory.py backend/tests/unit/engine/test_load_memory.py && git commit -m "feat(m3b): load_memory node with timeout fallback"
```

---

### Task 7: rank_and_select Uses State Weights

**Files:**
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py:15,194,234`
- Modify: `backend/tests/unit/engine/test_rank_and_select.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/engine/test_rank_and_select.py — append

@pytest.mark.asyncio
async def test_rank_and_select_uses_state_weights() -> None:
    """When state has objective_weights, those are used instead of DEFAULT_WEIGHTS."""
    # Create a state with custom weights that heavily favor novelty
    custom_weights = {
        "voice_leading": 0.05,
        "register_density": 0.05,
        "playability": 0.05,
        "genre_fit": 0.05,
        "emotional_fit": 0.05,
        "theoretical_coherence": 0.05,
        "cadence_quality": 0.05,
        "novelty": 0.60,
        "loopability": 0.05,
    }

    # Candidate A: high novelty, low genre_fit
    # Candidate B: low novelty, high genre_fit
    prog_a = {
        "id": "prog_a",
        "chord_symbols": ["C", "G"],
        "metadata": {"scores": {"genre_fit": 3.0, "novelty": 9.5, "emotional_fit": 5.0, "theoretical_coherence": 5.0, "cadence_quality": 5.0, "loopability": 5.0}},
    }
    prog_b = {
        "id": "prog_b",
        "chord_symbols": ["Am", "F"],
        "metadata": {"scores": {"genre_fit": 9.5, "novelty": 3.0, "emotional_fit": 5.0, "theoretical_coherence": 5.0, "cadence_quality": 5.0, "loopability": 5.0}},
    }

    arr_a = {"id": "arr_a", "progression_candidate_id": "prog_a", "status": "draft"}
    arr_b = {"id": "arr_b", "progression_candidate_id": "prog_b", "status": "draft"}

    eval_a = {
        "arrangement_candidate_id": "arr_a",
        "voice_leading": {"overall_score": 7.0},
        "register_density": {"overall_score": 7.0},
        "playability": {"overall_score": 7.0},
    }
    eval_b = {
        "arrangement_candidate_id": "arr_b",
        "voice_leading": {"overall_score": 7.0},
        "register_density": {"overall_score": 7.0},
        "playability": {"overall_score": 7.0},
    }

    state = {
        "arrangement_candidates": [arr_a, arr_b],
        "arrangement_families": [],
        "progression_candidates": [prog_a, prog_b],
        "evaluations": [eval_a, eval_b],
        "objective_weights": custom_weights,
    }

    from explorator.engine.nodes.rank_and_select import rank_and_select
    result = await rank_and_select(state)

    # With 60% weight on novelty, candidate A (novelty=9.5) should rank higher
    scorecards = result["scorecards"]
    sc_a = next(sc for sc in scorecards if sc["candidate_id"] == "arr_a")
    sc_b = next(sc for sc in scorecards if sc["candidate_id"] == "arr_b")
    assert sc_a["weighted_total"] > sc_b["weighted_total"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_rank_and_select.py::test_rank_and_select_uses_state_weights -v`
Expected: FAIL — rank_and_select ignores state weights, uses DEFAULT_WEIGHTS

- [ ] **Step 3: Modify rank_and_select to read weights from state**

In `backend/src/explorator/engine/nodes/rank_and_select.py`, change `rank_and_select()`:

Replace the line (around line 194):
```python
        selected_in_family = _rank_family(family_candidates, DEFAULT_WEIGHTS)
```
With:
```python
        selected_in_family = _rank_family(family_candidates, weights)
```

Replace the line (around line 234):
```python
            weighted_total = _compute_weighted_total(merged, DEFAULT_WEIGHTS)
```
With:
```python
            weighted_total = _compute_weighted_total(merged, weights)
```

Add near the top of `rank_and_select()`, after reading state fields:
```python
    # M3b: use state-provided weights if available, else hardcoded defaults
    weights: dict[str, float] = state.get("objective_weights", DEFAULT_WEIGHTS)
```

- [ ] **Step 4: Run full rank_and_select tests**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_rank_and_select.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/engine/nodes/rank_and_select.py backend/tests/unit/engine/test_rank_and_select.py && git commit -m "feat(m3b): rank_and_select reads objective_weights from state"
```

---

### Task 8: check_stop — User Satisfaction Condition

**Files:**
- Modify: `backend/src/explorator/engine/nodes/check_stop.py`
- Modify: `backend/tests/unit/engine/test_check_stop.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/engine/test_check_stop.py — append

async def test_stop_on_user_satisfaction() -> None:
    """Stop when recent feedback indicates positive satisfaction."""
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    state["feedback_history"] = [
        {
            "id": "fb_1",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "positive"},
        },
    ]
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "satisfaction"


async def test_no_stop_on_neutral_feedback() -> None:
    """Neutral feedback does not trigger satisfaction stop."""
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    state["feedback_history"] = [
        {
            "id": "fb_1",
            "candidate_id": "a",
            "interpreted_adjustments": {"satisfaction": "neutral"},
        },
    ]
    result = await check_stop(state)
    assert result["stop_condition_met"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_check_stop.py::test_stop_on_user_satisfaction -v`
Expected: FAIL — check_stop doesn't check feedback_history

- [ ] **Step 3: Add satisfaction check to check_stop**

In `backend/src/explorator/engine/nodes/check_stop.py`, add after condition 3 (budget, before the final `return`):

```python
    # Condition 4: User satisfaction (M3b)
    feedback_history = state.get("feedback_history", [])
    for fb in feedback_history:
        adjustments = fb.get("interpreted_adjustments", {})
        if adjustments.get("satisfaction") == "positive":
            logger.info("Stop: user expressed satisfaction in feedback %s", fb.get("id", "?"))
            return {"stop_condition_met": True, "stop_reason": "satisfaction"}
```

- [ ] **Step 4: Run all check_stop tests**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_check_stop.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/engine/nodes/check_stop.py backend/tests/unit/engine/test_check_stop.py && git commit -m "feat(m3b): add user satisfaction stop condition to check_stop"
```

---

### Task 9: Wire load_memory into Graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/tests/unit/engine/test_unified_graph.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/engine/test_unified_graph.py — append

def test_load_memory_node_exists_in_graph() -> None:
    """load_memory is registered between load_genre and generate."""
    from unittest.mock import AsyncMock
    from explorator.engine.graph import build_exploration_graph

    gemini = AsyncMock()
    driver = AsyncMock()
    graph = build_exploration_graph(gemini, driver)

    node_names = list(graph.nodes.keys())
    assert "load_memory" in node_names

    # load_memory should come after load_genre
    lm_idx = node_names.index("load_memory")
    lg_idx = node_names.index("load_genre")
    gen_idx = node_names.index("generate")
    assert lg_idx < lm_idx < gen_idx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_unified_graph.py::test_load_memory_node_exists_in_graph -v`
Expected: FAIL — `load_memory` not in graph

- [ ] **Step 3: Add load_memory to graph**

In `backend/src/explorator/engine/graph.py`:

Add import at top:
```python
from explorator.engine.nodes.load_memory import load_memory
```

In `build_exploration_graph()`, after the M1 nodes block, add the load_memory node:
```python
    # M3b: memory/feedback node
    graph.add_node("load_memory", partial(load_memory, driver=driver))
```

Change the edge from `load_genre → generate` to `load_genre → load_memory → generate`:
Replace:
```python
    graph.add_edge("load_genre", "generate")
```
With:
```python
    graph.add_edge("load_genre", "load_memory")
    graph.add_edge("load_memory", "generate")
```

- [ ] **Step 4: Run unified graph tests**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/engine/test_unified_graph.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/engine/graph.py backend/tests/unit/engine/test_unified_graph.py && git commit -m "feat(m3b): wire load_memory node between load_genre and generate"
```

---

### Task 10: Feedback API Endpoint

**Files:**
- Create: `backend/src/explorator/api/routes/feedback.py`
- Modify: `backend/src/explorator/api/app.py`

- [ ] **Step 1: Implement the endpoint**

```python
# backend/src/explorator/api/routes/feedback.py
"""API route for user feedback submission."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
from explorator.domain.intent.feedback import FeedbackInterpreter, apply_weight_deltas
from explorator.graph.feedback_repo import FeedbackEventRepo, ObjectiveWeightsRepo
from explorator.graph.session_repo import SessionRepository
from explorator.models.evaluation import ObjectiveWeights
from explorator.models.memory import UserFeedbackEvent
from explorator.utils import utc_now

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])


class SubmitFeedbackRequest(BaseModel):
    candidate_id: str
    content: str
    feedback_type: str = "text_reaction"


class FeedbackResponse(BaseModel):
    id: str
    interpreted_adjustments: dict[str, Any]
    adjusted_weights: dict[str, float]
    satisfaction: str


@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(
    session_id: str,
    request: SubmitFeedbackRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> FeedbackResponse:
    """Submit user feedback on a candidate. Interprets via Gemini Flash and reweights."""
    session_repo = SessionRepository(driver)
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load current weights
    ow_repo = ObjectiveWeightsRepo(driver)
    latest = await ow_repo.get_latest_for_session(session_id)
    current_weights = (
        latest["weights"]
        if latest and "weights" in latest
        else dict(CANONICAL_DEFAULT_WEIGHTS.weights)
    )

    # Get candidate scores for context
    fb_repo = FeedbackEventRepo(driver)
    candidate_scores: dict[str, float] = {}  # Best-effort; scores may not be on candidate node

    # Interpret feedback via Gemini Flash
    interpreter = FeedbackInterpreter(gemini)
    interpretation = await interpreter.interpret(
        feedback_text=request.content,
        current_weights=current_weights,
        candidate_scores=candidate_scores,
        genre=session.get("genre", ""),
    )

    # Apply weight deltas
    adjusted_weights = apply_weight_deltas(current_weights, interpretation.weight_deltas)

    # Persist UserFeedbackEvent
    now = utc_now()
    feedback_id = f"fb_{ULID()}"
    # Merge satisfaction into interpreted_adjustments for persistence (spec 4.8)
    adjustments_with_satisfaction = dict(interpretation.interpreted_adjustments)
    adjustments_with_satisfaction["satisfaction"] = interpretation.satisfaction

    event = UserFeedbackEvent(
        id=feedback_id,
        type="user_feedback_event",
        status="active",
        created_at=now,
        updated_at=now,
        session_id=session_id,
        candidate_id=request.candidate_id,
        feedback_type=request.feedback_type,
        content=request.content,
        interpreted_adjustments=adjustments_with_satisfaction,
        weight_deltas=dict(interpretation.weight_deltas),
    )
    await fb_repo.create(event)

    # Persist new ObjectiveWeights
    # Count existing feedback to determine round number
    existing_feedback = await fb_repo.list_by_session(session_id)
    round_n = len(existing_feedback)

    weights_id = f"ow_{ULID()}"
    weights_entity = ObjectiveWeights(
        id=weights_id,
        type="objective_weights",
        status="active",
        created_at=now,
        updated_at=now,
        profile_name=f"session_{session_id}_round_{round_n}",
        weights=adjusted_weights,
    )
    await ow_repo.create(weights_entity)

    # Create Neo4j relationships (spec 4.6)
    async with driver.session() as neo_session:
        await neo_session.run(
            "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (c {id: $cand_id}) "
            "CREATE (fb)-[:ABOUT]->(c)",
            fb_id=feedback_id, cand_id=request.candidate_id,
        )
        await neo_session.run(
            "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (ow:ObjectiveWeights {id: $ow_id}) "
            "CREATE (fb)-[:UPDATES]->(ow)",
            fb_id=feedback_id, ow_id=weights_id,
        )
        await neo_session.run(
            "MATCH (s:Session {id: $sess_id}), (fb:UserFeedbackEvent {id: $fb_id}) "
            "CREATE (s)-[:HAS_FEEDBACK]->(fb)",
            sess_id=session_id, fb_id=feedback_id,
        )

    return FeedbackResponse(
        id=feedback_id,
        interpreted_adjustments=dict(interpretation.interpreted_adjustments),
        adjusted_weights=adjusted_weights,
        satisfaction=interpretation.satisfaction,
    )
```

- [ ] **Step 2: Register the router in app.py**

In `backend/src/explorator/api/app.py`, add import:
```python
from explorator.api.routes.feedback import router as feedback_router
```

Add after the mutations router line:
```python
    app.include_router(feedback_router, prefix="/v1")
```

- [ ] **Step 3: Run the existing test suite to verify no regressions**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/unit/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add backend/src/explorator/api/routes/feedback.py backend/src/explorator/api/app.py && git commit -m "feat(m3b): POST /v1/sessions/{session_id}/feedback endpoint"
```

---

### Task 11: Frontend — Feedback Store

**Files:**
- Create: `frontend/src/stores/feedbackStore.ts`

- [ ] **Step 1: Implement the store**

```typescript
// frontend/src/stores/feedbackStore.ts
import { create } from 'zustand';

export interface FeedbackEntry {
  id: string;
  content: string;
  interpreted_adjustments: Record<string, unknown>;
  adjusted_weights: Record<string, number>;
  satisfaction: string;
  timestamp: string;
}

interface FeedbackState {
  entries: FeedbackEntry[];
  currentWeights: Record<string, number> | null;
  submitting: boolean;
  error: string | null;
  addEntry: (entry: FeedbackEntry) => void;
  setCurrentWeights: (weights: Record<string, number>) => void;
  setSubmitting: (submitting: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useFeedbackStore = create<FeedbackState>((set) => ({
  entries: [],
  currentWeights: null,
  submitting: false,
  error: null,
  addEntry: (entry) =>
    set((state) => ({
      entries: [...state.entries, entry],
      currentWeights: entry.adjusted_weights,
    })),
  setCurrentWeights: (weights) => set({ currentWeights: weights }),
  setSubmitting: (submitting) => set({ submitting }),
  setError: (error) => set({ error }),
  reset: () => set({ entries: [], currentWeights: null, submitting: false, error: null }),
}));
```

- [ ] **Step 2: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add frontend/src/stores/feedbackStore.ts && git commit -m "feat(m3b): Zustand feedback store"
```

---

### Task 12: Frontend — API + SSE for Feedback

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/services/sse.ts`

- [ ] **Step 1: Add submitFeedback to api.ts**

Append to `frontend/src/services/api.ts`:

```typescript
// --- M3b Feedback Types ---

export interface FeedbackResponse {
  id: string;
  interpreted_adjustments: Record<string, unknown>;
  adjusted_weights: Record<string, number>;
  satisfaction: string;
}

export async function submitFeedback(
  sessionId: string,
  candidateId: string,
  content: string,
): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      candidate_id: candidateId,
      content,
      feedback_type: 'text_reaction',
    }),
  });
  if (!res.ok) throw new Error(`Feedback submission failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Add feedback_processed to SSE types**

In `frontend/src/services/sse.ts`, update the `SSEEventType` union:

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
  | 'feedback_processed';
```

- [ ] **Step 3: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add frontend/src/services/api.ts frontend/src/services/sse.ts && git commit -m "feat(m3b): frontend API client and SSE type for feedback"
```

---

### Task 13: Frontend — FeedbackSidebar Component

**Files:**
- Create: `frontend/src/components/FeedbackSidebar.tsx`

- [ ] **Step 1: Implement the sidebar**

```tsx
// frontend/src/components/FeedbackSidebar.tsx
import { useState, useRef, useEffect } from 'react';
import { useFeedbackStore } from '../stores/feedbackStore';
import { submitFeedback } from '../services/api';
import type { FeedbackEntry } from '../stores/feedbackStore';

interface FeedbackSidebarProps {
  sessionId: string;
  candidateId: string | null;
}

const DIMENSION_LABELS: Record<string, string> = {
  genre_fit: 'Genre Fit',
  emotional_fit: 'Emotional',
  theoretical_coherence: 'Theory',
  cadence_quality: 'Cadence',
  novelty: 'Novelty',
  loopability: 'Loopability',
  voice_leading: 'Voice Lead.',
  register_density: 'Register',
  playability: 'Playability',
};

function WeightBar({ dimension, weight, delta }: { dimension: string; weight: number; delta?: number }) {
  const pct = Math.round(weight * 100);
  const label = DIMENSION_LABELS[dimension] || dimension;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 truncate" title={dimension}>{label}</span>
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-purple-500 rounded-full transition-all duration-300"
          style={{ width: `${pct * 2}%` }}
        />
      </div>
      <span className="w-10 text-right text-gray-400">{pct}%</span>
      {delta !== undefined && delta !== 0 && (
        <span className={`w-10 text-right text-xs ${delta > 0 ? 'text-green-400' : 'text-red-400'}`}>
          {delta > 0 ? '+' : ''}{(delta * 100).toFixed(0)}
        </span>
      )}
    </div>
  );
}

function FeedbackMessage({ entry }: { entry: FeedbackEntry }) {
  const adjustments = entry.interpreted_adjustments;
  const summary = Object.entries(adjustments)
    .filter(([k]) => k !== 'satisfaction')
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
    .join(', ');

  return (
    <div className="space-y-1">
      <div className="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200">
        {entry.content}
      </div>
      {summary && (
        <div className="bg-purple-900/30 border border-purple-800/50 rounded-lg px-3 py-2 text-xs text-purple-300">
          Understood: {summary}
        </div>
      )}
    </div>
  );
}

export default function FeedbackSidebar({ sessionId, candidateId }: FeedbackSidebarProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const { entries, currentWeights, submitting, error, addEntry, setSubmitting, setError } = useFeedbackStore();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [entries.length]);

  const handleSubmit = async () => {
    if (!input.trim() || !candidateId || submitting) return;
    const text = input.trim();
    setInput('');
    setSubmitting(true);
    setError(null);

    try {
      const response = await submitFeedback(sessionId, candidateId, text);
      addEntry({
        id: response.id,
        content: text,
        interpreted_adjustments: response.interpreted_adjustments,
        adjusted_weights: response.adjusted_weights,
        satisfaction: response.satisfaction,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit feedback');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-80 border-l border-gray-800 bg-gray-950 flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800">
        <h3 className="text-sm font-semibold text-gray-300">Feedback</h3>
        <p className="text-xs text-gray-600 mt-0.5">Tell me what to change</p>
      </div>

      {/* Weight visualization */}
      {currentWeights && (
        <div className="px-4 py-3 border-b border-gray-800 space-y-1.5">
          <h4 className="text-xs font-medium text-gray-500 mb-2">Current Weights</h4>
          {Object.entries(currentWeights).map(([dim, weight]) => (
            <WeightBar key={dim} dimension={dim} weight={weight} />
          ))}
        </div>
      )}

      {/* Chat thread */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {entries.length === 0 && (
          <p className="text-xs text-gray-600 text-center py-8">
            No feedback yet. Type below to steer the search.
          </p>
        )}
        {entries.map((entry) => (
          <FeedbackMessage key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 text-xs text-red-400 bg-red-900/20">
          {error}
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
            placeholder={candidateId ? 'e.g. "more experimental"' : 'Select a candidate first'}
            disabled={!candidateId || submitting}
            className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || !candidateId || submitting}
            className="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-500 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add frontend/src/components/FeedbackSidebar.tsx && git commit -m "feat(m3b): FeedbackSidebar component with weight visualization"
```

---

### Task 14: Integrate FeedbackSidebar into SessionWorkspace

**Files:**
- Modify: `frontend/src/views/SessionWorkspace.tsx`

- [ ] **Step 1: Add import and state**

At the top of `SessionWorkspace.tsx`, add imports:
```typescript
import FeedbackSidebar from '../components/FeedbackSidebar';
import { useFeedbackStore } from '../stores/feedbackStore';
```

- [ ] **Step 2: Add feedback sidebar to realization view**

In the `viewMode === 'realization'` branch, wrap the existing split panel with the feedback sidebar. Change:

```tsx
      {viewMode === 'realization' ? (
        <>
          {/* Back button */}
          <button
            onClick={() => {
              setViewMode('generation');
              audioEngine.stop();
              arrangementStore.reset();
            }}
            className="text-xs text-slate-500 hover:text-slate-300 mb-2"
          >
            &larr; Back to progressions
          </button>
          {/* Split panel */}
          <div className="flex flex-1 min-h-0 rounded-lg overflow-hidden border border-slate-700">
            <ArrangementList
              arrangements={arrangementStore.arrangements}
              candidates={candidates}
              selectedId={arrangementStore.selectedArrangementId}
              onSelect={handleSelectArrangement}
              genre={session?.genre || 'dream_pop'}
            />
            <ArrangementDetail
              arrangement={arrangementStore.selectedDetail}
              genre={session?.genre || 'dream_pop'}
            />
          </div>
        </>
```

To:

```tsx
      {viewMode === 'realization' ? (
        <>
          {/* Back button */}
          <button
            onClick={() => {
              setViewMode('generation');
              audioEngine.stop();
              arrangementStore.reset();
              useFeedbackStore.getState().reset();
            }}
            className="text-xs text-slate-500 hover:text-slate-300 mb-2"
          >
            &larr; Back to progressions
          </button>
          {/* Split panel + feedback sidebar */}
          <div className="flex flex-1 min-h-0 rounded-lg overflow-hidden border border-slate-700">
            <ArrangementList
              arrangements={arrangementStore.arrangements}
              candidates={candidates}
              selectedId={arrangementStore.selectedArrangementId}
              onSelect={handleSelectArrangement}
              genre={session?.genre || 'dream_pop'}
            />
            <ArrangementDetail
              arrangement={arrangementStore.selectedDetail}
              genre={session?.genre || 'dream_pop'}
            />
            {sessionId && (
              <FeedbackSidebar
                sessionId={sessionId}
                candidateId={arrangementStore.selectedArrangementId}
              />
            )}
          </div>
        </>
```

- [ ] **Step 3: Verify frontend compiles**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /home/angel/Documents/code/Explorator && git add frontend/src/views/SessionWorkspace.tsx && git commit -m "feat(m3b): integrate FeedbackSidebar in realization view"
```

---

### Task 15: Full Backend Test Suite Regression Check

**Files:** None (verification only)

- [ ] **Step 1: Run the complete backend test suite**

Run: `cd /home/angel/Documents/code/Explorator/backend && python -m pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 2: Run frontend build check**

Run: `cd /home/angel/Documents/code/Explorator/frontend && npx tsc --noEmit && npm run build`
Expected: No errors

- [ ] **Step 3: If failures, fix and commit**

Fix any failures found. Create a dedicated fix commit per issue.
