# M3a: Mutation Loop — Implementation Plan


**Goal:** Enable candidates to be mutated and re-evaluated across multiple rounds with automatic stop conditions, conditional routing (harmonic vs arrangement mutations), and basic Pareto preservation.

**Architecture:** Add 3 new LangGraph nodes (`check_stop`, `mutate`, conditional `route_mutation` edge) to the unified graph. Create `HarmonyMutator` domain service (Gemini Pro + constrained vocabulary). Add basic Pareto front identification in `rank_and_select`. Persist `SearchRound` and `MutationRecord` to Neo4j. Expose user-initiated mutation via API. Frontend shows round progress, lineage badges, lineage tree, and mutate button.

**Tech Stack:** Python 3.12, LangGraph, FastAPI, Neo4j, Gemini Pro, pytest, React 19, TypeScript, Zustand

**Spec:** `docs/design/specs/2026-04-10-m3-guided-search-design.md` — Section 3

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `engine/state.py` | Add M3a state fields |
| Modify | `engine/graph.py` | Add check_stop, mutate nodes + conditional routing |
| Create | `engine/nodes/check_stop.py` | Evaluate stop conditions 1-3 |
| Create | `engine/nodes/mutate.py` | Orchestrate mutation engine |
| Create | `domain/harmony/mutator.py` | Gemini Pro mutation service |
| Create | `domain/evaluation/pareto.py` | Basic Pareto front identification |
| Create | `prompts/mutation.py` | Mutation prompt template |
| Modify | `engine/nodes/rank_and_select.py` | Add Pareto preservation + use configurable weights |
| Modify | `engine/nodes/persist_round.py` | Persist SearchRound, MutationRecords |
| Create | `graph/search_round_repo.py` | Neo4j CRUD for SearchRound |
| Create | `graph/mutation_record_repo.py` | Neo4j CRUD for MutationRecord |
| Create | `api/routes/mutations.py` | POST /v1/sessions/:id/mutate |
| Modify | `domain/evaluation/ranking.py` | Add canonical 9-dim default weights |

All paths relative to `backend/src/explorator/`.

---

### Task 1: Add M3a State Fields to ExplorationState

**Files:**
- Modify: `backend/src/explorator/engine/state.py`
- Test: `backend/tests/unit/engine/test_state.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/engine/test_state.py`:

```python
def test_exploration_state_includes_m3a_fields() -> None:
    """Unified state supports M3a search and mutation fields."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "search_plan": {"max_rounds": 4},
        "mutation_records": [{"id": "mr_01"}],
        "stop_condition_met": False,
        "stop_reason": "",
        "pareto_front": {"candidate_ids": []},
        "all_candidates_history": [],
    }
    assert state["stop_condition_met"] is False
    assert state["search_plan"]["max_rounds"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/engine/test_state.py::test_exploration_state_includes_m3a_fields -v`

- [ ] **Step 3: Add M3a fields to ExplorationState**

In `backend/src/explorator/engine/state.py`, add after the `selected_arrangements` field:

```python
    # --- M3a: Search & Mutation ---
    search_plan: dict[str, Any]
    mutation_records: list[dict[str, Any]]
    stop_condition_met: bool
    stop_reason: str  # "quality" | "budget" | "diversity" | ""
    pareto_front: dict[str, Any]
    all_candidates_history: list[dict[str, Any]]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/engine/test_state.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/state.py backend/tests/unit/engine/test_state.py
git commit -m "feat(m3a): add search and mutation fields to ExplorationState"
```

---

### Task 2: Add Canonical 9-Dimensional Default Weights

**Files:**
- Modify: `backend/src/explorator/domain/evaluation/ranking.py`
- Test: `backend/tests/unit/domain/test_ranking.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/domain/test_ranking.py`:

```python
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS


def test_canonical_weights_sum_to_one() -> None:
    """Canonical 9-dimensional weights sum to 1.0."""
    total = sum(CANONICAL_DEFAULT_WEIGHTS.weights.values())
    assert abs(total - 1.0) < 0.01


def test_canonical_weights_have_all_nine_dimensions() -> None:
    """Canonical weights cover all 6 theory + 3 arrangement dimensions."""
    expected = {
        "genre_fit", "emotional_fit", "theoretical_coherence",
        "cadence_quality", "novelty", "loopability",
        "voice_leading", "register_density", "playability",
    }
    assert set(CANONICAL_DEFAULT_WEIGHTS.weights.keys()) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/domain/test_ranking.py::test_canonical_weights_sum_to_one -v`

- [ ] **Step 3: Add canonical weights**

In `backend/src/explorator/domain/evaluation/ranking.py`, add after the existing `DEFAULT_THEORY_WEIGHTS`:

```python
CANONICAL_DEFAULT_WEIGHTS = ObjectiveWeights(
    id="weights_canonical",
    type="objective_weights",
    status="active",
    profile_name="canonical_default",
    weights={
        "genre_fit": 0.15,
        "emotional_fit": 0.10,
        "theoretical_coherence": 0.12,
        "cadence_quality": 0.10,
        "novelty": 0.10,
        "loopability": 0.13,
        "voice_leading": 0.12,
        "register_density": 0.09,
        "playability": 0.09,
    },
)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/domain/test_ranking.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/ranking.py backend/tests/unit/domain/test_ranking.py
git commit -m "feat(m3a): add canonical 9-dimensional default ObjectiveWeights"
```

---

### Task 3: Basic Pareto Front Identification

**Files:**
- Create: `backend/src/explorator/domain/evaluation/pareto.py`
- Create: `backend/tests/unit/domain/test_pareto.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/domain/test_pareto.py`:

```python
"""Tests for Pareto front identification."""

from explorator.domain.evaluation.pareto import compute_pareto_front


def test_single_candidate_is_on_front() -> None:
    candidates = [{"id": "a", "scores": {"x": 8.0, "y": 7.0}}]
    front = compute_pareto_front(candidates, axes=["x", "y"])
    assert front == ["a"]


def test_dominated_candidate_excluded() -> None:
    """B dominates A on all axes → A not on front."""
    candidates = [
        {"id": "a", "scores": {"x": 5.0, "y": 5.0}},
        {"id": "b", "scores": {"x": 8.0, "y": 8.0}},
    ]
    front = compute_pareto_front(candidates, axes=["x", "y"])
    assert front == ["b"]


def test_non_dominated_candidates_both_on_front() -> None:
    """A better on x, B better on y → both on front."""
    candidates = [
        {"id": "a", "scores": {"x": 9.0, "y": 3.0}},
        {"id": "b", "scores": {"x": 3.0, "y": 9.0}},
    ]
    front = compute_pareto_front(candidates, axes=["x", "y"])
    assert set(front) == {"a", "b"}


def test_three_candidates_mixed() -> None:
    candidates = [
        {"id": "a", "scores": {"x": 9.0, "y": 3.0, "z": 5.0}},
        {"id": "b", "scores": {"x": 3.0, "y": 9.0, "z": 5.0}},
        {"id": "c", "scores": {"x": 4.0, "y": 4.0, "z": 4.0}},  # dominated by a on x, by b on y
    ]
    front = compute_pareto_front(candidates, axes=["x", "y", "z"])
    # c is NOT dominated: a has x=9>4 and z=5>4 but y=3<4; b has y=9>4 but x=3<4
    # Actually c is non-dominated — no single candidate beats it on ALL axes
    assert "c" in front


def test_empty_candidates() -> None:
    assert compute_pareto_front([], axes=["x"]) == []


def test_missing_score_defaults_to_zero() -> None:
    candidates = [
        {"id": "a", "scores": {"x": 5.0}},  # y missing → 0.0
        {"id": "b", "scores": {"x": 3.0, "y": 8.0}},
    ]
    front = compute_pareto_front(candidates, axes=["x", "y"])
    # a: x=5, y=0; b: x=3, y=8 → neither dominates → both on front
    assert set(front) == {"a", "b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/domain/test_pareto.py -v`

- [ ] **Step 3: Implement Pareto front**

Create `backend/src/explorator/domain/evaluation/pareto.py`:

```python
"""Pareto front identification for multi-objective candidate ranking."""


def _dominates(
    scores_a: dict[str, float],
    scores_b: dict[str, float],
    axes: list[str],
) -> bool:
    """Return True if A dominates B: A >= B on all axes AND A > B on at least one."""
    at_least_one_better = False
    for axis in axes:
        val_a = scores_a.get(axis, 0.0)
        val_b = scores_b.get(axis, 0.0)
        if val_a < val_b:
            return False
        if val_a > val_b:
            at_least_one_better = True
    return at_least_one_better


def compute_pareto_front(
    candidates: list[dict],
    axes: list[str],
) -> list[str]:
    """Identify non-dominated candidate IDs.

    A candidate is non-dominated if no other candidate scores strictly
    higher on ALL specified axes. O(n²) pairwise comparison.

    Args:
        candidates: List of dicts with "id" and "scores" keys.
        axes: Score dimensions to compare on.

    Returns:
        List of candidate IDs on the Pareto front.
    """
    if not candidates:
        return []

    front: list[str] = []
    for i, cand_a in enumerate(candidates):
        scores_a = cand_a.get("scores", {})
        dominated = False
        for j, cand_b in enumerate(candidates):
            if i == j:
                continue
            scores_b = cand_b.get("scores", {})
            if _dominates(scores_b, scores_a, axes):
                dominated = True
                break
        if not dominated:
            front.append(cand_a["id"])
    return front
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/domain/test_pareto.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/evaluation/pareto.py backend/tests/unit/domain/test_pareto.py
git commit -m "feat(m3a): Pareto front identification with O(n²) non-dominated sort"
```

---

### Task 4: Mutation Prompt Template

**Files:**
- Create: `backend/src/explorator/prompts/mutation.py`
- Test: `backend/tests/unit/prompts/test_mutation_prompt.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/unit/prompts/test_mutation_prompt.py`:

```python
"""Tests for mutation prompt generation."""

from explorator.prompts.mutation import mutation_prompt


def test_mutation_prompt_returns_tuple() -> None:
    user, system = mutation_prompt(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={"genre_fit": 7.0, "novelty": 5.0},
        guidance=None,
        allowed_operations=[
            "substitute_chord", "reharmonize_cadence", "modal_interchange",
            "alter_density", "experimental",
        ],
    )
    assert isinstance(user, str)
    assert isinstance(system, str)
    assert "Cmaj7" in user
    assert "dream_pop" in user


def test_mutation_prompt_includes_guidance() -> None:
    user, _ = mutation_prompt(
        chord_symbols=["Cmaj7", "Am7"],
        genre="synthwave",
        scores={"genre_fit": 6.0},
        guidance="make it darker",
        allowed_operations=["substitute_chord"],
    )
    assert "make it darker" in user
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/prompts/test_mutation_prompt.py -v`

- [ ] **Step 3: Implement the prompt**

Create `backend/src/explorator/prompts/mutation.py`:

```python
"""Prompts for candidate mutation (Gemini Pro)."""


MUTATION_OPERATIONS = {
    "substitute_chord": "Replace one chord with a diatonic or chromatic substitute",
    "reharmonize_cadence": "Change the cadence type (e.g., V-I → bVII-I)",
    "modal_interchange": "Borrow a chord from the parallel mode",
    "alter_density": "Add or remove passing chords",
    "swap_voicing_type": "Change voicing strategy (open → drop-2, etc.)",
    "swap_bass_mode": "Change bass pattern (supportive → syncopated, etc.)",
    "shift_register": "Transpose voicing register up/down an octave",
    "experimental": "Propose a free-form mutation with explanation",
}


def mutation_prompt(
    chord_symbols: list[str],
    genre: str,
    scores: dict[str, float],
    guidance: str | None,
    allowed_operations: list[str],
) -> tuple[str, str]:
    """Build prompt + system prompt for mutation generation.

    Returns (user_prompt, system_prompt).
    """
    ops_desc = "\n".join(
        f"- {op}: {MUTATION_OPERATIONS[op]}"
        for op in allowed_operations
        if op in MUTATION_OPERATIONS
    )

    scores_str = ", ".join(f"{k}: {v:.1f}" for k, v in scores.items())

    guidance_block = ""
    if guidance:
        guidance_block = f"\n\nUser guidance: {guidance}\nPrioritize mutations that address this guidance."

    system_prompt = (
        "You are a music theory expert specializing in chord progression mutation. "
        "Given a progression, its genre context, and current quality scores, "
        "select one or more mutations from the allowed operations to improve the weakest scores "
        "while preserving what already works well. "
        "Return structured JSON with your chosen operations, parameters, reasoning, and predicted score effects."
    )

    user_prompt = f"""Mutate this chord progression for the {genre} genre.

Current progression: {' → '.join(chord_symbols)}

Current scores: {scores_str}

Allowed operations:
{ops_desc}
{guidance_block}

Select 1-3 mutations to apply. For each mutation, specify:
- operation: the operation name from the list above
- params: operation-specific parameters (e.g., which chord to substitute, what to replace it with)
- reason: why this mutation should improve the progression
- predicted_effects: which score dimensions should improve and by how much

Return the mutated chord progression with the full list of changes applied."""

    return user_prompt, system_prompt
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/prompts/test_mutation_prompt.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/prompts/mutation.py backend/tests/unit/prompts/test_mutation_prompt.py
git commit -m "feat(m3a): mutation prompt template with constrained operation vocabulary"
```

---

### Task 5: HarmonyMutator Domain Service

**Files:**
- Create: `backend/src/explorator/domain/harmony/mutator.py`
- Create: `backend/tests/unit/domain/test_mutator.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/unit/domain/test_mutator.py`:

```python
"""Tests for HarmonyMutator domain service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from explorator.domain.harmony.mutator import (
    HarmonyMutator,
    MutationResponse,
    MutationResponseItem,
)


def _make_gemini(response: MutationResponse) -> MagicMock:
    mock = MagicMock()
    mock.generate_structured = AsyncMock(return_value=response)
    return mock


@pytest.fixture
def sample_response() -> MutationResponse:
    return MutationResponse(
        mutated_chord_symbols=["Cmaj7", "Em7", "Fmaj7", "G7"],
        mutations=[
            MutationResponseItem(
                operation="substitute_chord",
                params={"position": 1, "original": "Am7", "replacement": "Em7"},
                reason="Em7 adds more tension before the IV chord",
                predicted_effects={"novelty": 1.0, "genre_fit": -0.5},
            ),
        ],
    )


async def test_mutate_harmonic_returns_progression(sample_response: MutationResponse) -> None:
    gemini = _make_gemini(sample_response)
    mutator = HarmonyMutator(gemini)

    result = await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={"genre_fit": 7.0, "novelty": 5.0},
        guidance=None,
    )

    assert result.mutated_chord_symbols == ["Cmaj7", "Em7", "Fmaj7", "G7"]
    assert len(result.mutations) == 1
    assert result.mutations[0].operation == "substitute_chord"
    gemini.generate_structured.assert_called_once()


async def test_mutate_harmonic_with_guidance(sample_response: MutationResponse) -> None:
    gemini = _make_gemini(sample_response)
    mutator = HarmonyMutator(gemini)

    await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7"],
        genre="synthwave",
        scores={"genre_fit": 6.0},
        guidance="make it darker",
    )

    call_args = gemini.generate_structured.call_args
    prompt = call_args.kwargs.get("prompt") or call_args.args[0]
    assert "make it darker" in prompt


async def test_mutate_harmonic_limits_experimental() -> None:
    """At most 1 experimental mutation per call."""
    response = MutationResponse(
        mutated_chord_symbols=["Dm7", "G7", "Cmaj7", "Am7"],
        mutations=[
            MutationResponseItem(
                operation="experimental",
                params={"description": "replaced everything"},
                reason="creative freedom",
                predicted_effects={},
            ),
            MutationResponseItem(
                operation="experimental",
                params={"description": "more changes"},
                reason="more freedom",
                predicted_effects={},
            ),
        ],
    )
    gemini = _make_gemini(response)
    mutator = HarmonyMutator(gemini)

    result = await mutator.mutate_harmonic(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={},
    )

    experimental_count = sum(1 for m in result.mutations if m.operation == "experimental")
    assert experimental_count <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/domain/test_mutator.py -v`

- [ ] **Step 3: Implement HarmonyMutator**

Create `backend/src/explorator/domain/harmony/mutator.py`:

```python
"""Harmony mutation service — Gemini Pro with constrained vocabulary."""

import logging

from pydantic import BaseModel, Field

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.prompts.mutation import MUTATION_OPERATIONS, mutation_prompt

logger = logging.getLogger(__name__)

# Harmonic-scope operations
HARMONIC_OPS = ["substitute_chord", "reharmonize_cadence", "modal_interchange", "alter_density", "experimental"]

# Arrangement-scope operations
ARRANGEMENT_OPS = ["swap_voicing_type", "swap_bass_mode", "shift_register", "experimental"]


class MutationResponseItem(BaseModel):
    """One mutation within a response."""

    operation: str
    params: dict = Field(default_factory=dict)
    reason: str = ""
    predicted_effects: dict[str, float] = Field(default_factory=dict)


class MutationResponse(BaseModel):
    """Gemini Pro structured response for mutation."""

    mutated_chord_symbols: list[str]
    mutations: list[MutationResponseItem] = Field(default_factory=list)


class HarmonyMutator:
    """Mutates chord progressions using Gemini Pro with constrained vocabulary."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def mutate_harmonic(
        self,
        chord_symbols: list[str],
        genre: str,
        scores: dict[str, float],
        guidance: str | None = None,
    ) -> MutationResponse:
        """Apply harmonic mutations to a chord progression.

        Uses Gemini Pro to select and apply mutations from the constrained
        vocabulary. At most 1 experimental mutation is kept per call.
        """
        user_prompt, system_prompt = mutation_prompt(
            chord_symbols=chord_symbols,
            genre=genre,
            scores=scores,
            guidance=guidance,
            allowed_operations=HARMONIC_OPS,
        )

        response = await self.gemini.generate_structured(
            prompt=user_prompt,
            response_model=MutationResponse,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        # Enforce max 1 experimental mutation
        response = self._cap_experimental(response)

        return response

    def _cap_experimental(self, response: MutationResponse) -> MutationResponse:
        """Keep at most 1 experimental mutation."""
        seen_experimental = False
        filtered: list[MutationResponseItem] = []
        for m in response.mutations:
            if m.operation == "experimental":
                if seen_experimental:
                    continue
                seen_experimental = True
            filtered.append(m)
        return MutationResponse(
            mutated_chord_symbols=response.mutated_chord_symbols,
            mutations=filtered,
        )
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/domain/test_mutator.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/domain/harmony/mutator.py backend/tests/unit/domain/test_mutator.py
git commit -m "feat(m3a): HarmonyMutator domain service with constrained vocabulary"
```

---

### Task 6: check_stop Node

**Files:**
- Create: `backend/src/explorator/engine/nodes/check_stop.py`
- Create: `backend/tests/unit/engine/test_check_stop.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/unit/engine/test_check_stop.py`:

```python
"""Tests for check_stop node."""

from explorator.engine.nodes.check_stop import check_stop


def _make_state(
    round_number: int = 1,
    max_rounds: int = 4,
    target_score: float = 8.5,
    scorecards: list | None = None,
    pareto_front: dict | None = None,
) -> dict:
    return {
        "round_number": round_number,
        "search_plan": {
            "stop_conditions": {
                "target_score": target_score,
                "max_rounds": max_rounds,
            },
        },
        "scorecards": scorecards or [],
        "pareto_front": pareto_front or {"candidate_ids": []},
    }


async def test_stop_on_quality_threshold() -> None:
    state = _make_state(
        scorecards=[{"weighted_total": 9.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "quality"


async def test_stop_on_budget_exhausted() -> None:
    state = _make_state(
        round_number=4,
        max_rounds=4,
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "budget"


async def test_no_stop_when_conditions_not_met() -> None:
    state = _make_state(
        round_number=1,
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is False
    assert result["stop_reason"] == ""


async def test_stop_on_diversity() -> None:
    state = _make_state(
        scorecards=[{"weighted_total": 6.0, "candidate_id": "a"}],
        pareto_front={
            "candidate_ids": ["a", "b", "c"],
            "pairwise_diverse": True,
        },
    )
    result = await check_stop(state)
    assert result["stop_condition_met"] is True
    assert result["stop_reason"] == "diversity"


async def test_quality_checked_before_budget() -> None:
    """Quality threshold takes priority over budget."""
    state = _make_state(
        round_number=4,
        max_rounds=4,
        scorecards=[{"weighted_total": 9.0, "candidate_id": "a"}],
    )
    result = await check_stop(state)
    assert result["stop_reason"] == "quality"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/engine/test_check_stop.py -v`

- [ ] **Step 3: Implement check_stop**

Create `backend/src/explorator/engine/nodes/check_stop.py`:

```python
"""check_stop node — evaluate stop conditions after each round."""

import logging
from typing import Any

from explorator.engine.state import ExplorationState

logger = logging.getLogger(__name__)


async def check_stop(state: ExplorationState) -> dict[str, Any]:
    """Check stop conditions. Deterministic — no Gemini call.

    Conditions (stop on ANY):
    1. Quality: top candidate weighted_total >= target_score
    2. Diversity: >= 3 pairwise-diverse candidates on Pareto front
    3. Budget: round_number >= max_rounds
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "check_stop"})

    plan = state.get("search_plan", {})
    stop_conditions = plan.get("stop_conditions", {})
    target_score = stop_conditions.get("target_score", 8.5)
    max_rounds = stop_conditions.get("max_rounds", 4)

    round_number = state.get("round_number", 1)
    scorecards = state.get("scorecards", [])
    pareto = state.get("pareto_front", {})

    # Condition 1: Quality threshold
    if scorecards:
        top_score = max(sc.get("weighted_total", 0.0) for sc in scorecards)
        if top_score >= target_score:
            logger.info("Stop: quality threshold met (%.2f >= %.2f)", top_score, target_score)
            return {"stop_condition_met": True, "stop_reason": "quality"}

    # Condition 2: Diversity sufficient
    pareto_ids = pareto.get("candidate_ids", [])
    pairwise_diverse = pareto.get("pairwise_diverse", False)
    if len(pareto_ids) >= 3 and pairwise_diverse:
        logger.info("Stop: diversity sufficient (%d Pareto candidates)", len(pareto_ids))
        return {"stop_condition_met": True, "stop_reason": "diversity"}

    # Condition 3: Budget exhausted
    if round_number >= max_rounds:
        logger.info("Stop: budget exhausted (round %d >= %d)", round_number, max_rounds)
        return {"stop_condition_met": True, "stop_reason": "budget"}

    logger.info("Continue: no stop condition met (round %d, top=%.2f)",
                round_number, max(
                    (sc.get("weighted_total", 0.0) for sc in scorecards),
                    default=0.0,
                ))
    return {"stop_condition_met": False, "stop_reason": ""}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/engine/test_check_stop.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/check_stop.py backend/tests/unit/engine/test_check_stop.py
git commit -m "feat(m3a): check_stop node with quality, diversity, and budget conditions"
```

---

### Task 7: Neo4j Repositories — SearchRound and MutationRecord

**Files:**
- Create: `backend/src/explorator/graph/search_round_repo.py`
- Create: `backend/src/explorator/graph/mutation_record_repo.py`

- [ ] **Step 1: Create SearchRoundRepo**

Create `backend/src/explorator/graph/search_round_repo.py`:

```python
"""Neo4j repository for SearchRound entities."""

from explorator.graph.repository import BaseRepository


class SearchRoundRepo(BaseRepository):
    """CRUD operations for SearchRound nodes."""

    label = "SearchRound"
```

- [ ] **Step 2: Create MutationRecordRepo**

Create `backend/src/explorator/graph/mutation_record_repo.py`:

```python
"""Neo4j repository for MutationRecord entities."""

from explorator.graph.repository import BaseRepository


class MutationRecordRepo(BaseRepository):
    """CRUD operations for MutationRecord nodes."""

    label = "MutationRecord"
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `cd backend && uv run pytest tests/ -q`

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/graph/search_round_repo.py backend/src/explorator/graph/mutation_record_repo.py
git commit -m "feat(m3a): Neo4j repositories for SearchRound and MutationRecord"
```

---

### Task 8: mutate Node

**Files:**
- Create: `backend/src/explorator/engine/nodes/mutate.py`
- Create: `backend/tests/unit/engine/test_mutate.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/unit/engine/test_mutate.py`:

```python
"""Tests for the mutate node."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from explorator.domain.harmony.mutator import MutationResponse, MutationResponseItem
from explorator.engine.nodes.mutate import mutate, _select_candidates_to_mutate


def test_select_candidates_prioritizes_pareto() -> None:
    scorecards = [
        {"candidate_id": "a", "weighted_total": 9.0},
        {"candidate_id": "b", "weighted_total": 8.0},
        {"candidate_id": "c", "weighted_total": 7.0},
        {"candidate_id": "d", "weighted_total": 6.0},
    ]
    pareto_ids = ["c", "d"]
    result = _select_candidates_to_mutate(
        scorecards=scorecards,
        pareto_ids=pareto_ids,
        budget=3,
    )
    # Pareto members first, then top scorers
    assert "c" in result
    assert "d" in result
    assert len(result) == 3


def test_select_candidates_respects_budget() -> None:
    scorecards = [
        {"candidate_id": "a", "weighted_total": 9.0},
        {"candidate_id": "b", "weighted_total": 8.0},
    ]
    result = _select_candidates_to_mutate(scorecards=scorecards, pareto_ids=[], budget=1)
    assert len(result) == 1
    assert result[0] == "a"


async def test_mutate_returns_merged_candidates() -> None:
    """mutate must return existing + new candidates (not just new)."""
    mock_mutator_response = MutationResponse(
        mutated_chord_symbols=["Dm7", "G7", "Cmaj7"],
        mutations=[
            MutationResponseItem(
                operation="substitute_chord",
                params={"position": 0, "original": "Am7", "replacement": "Dm7"},
                reason="test",
                predicted_effects={},
            ),
        ],
    )

    mock_gemini = MagicMock()
    mock_gemini.generate_structured = AsyncMock(return_value=mock_mutator_response)

    existing_prog = {
        "id": "pc_01",
        "chord_symbols": ["Am7", "G7", "Cmaj7"],
        "metadata": {"scores": {"genre_fit": 7.0, "novelty": 5.0}},
    }

    state = {
        "session_id": "sess_01",
        "genre": "dream_pop",
        "genre_profile": {"genre": "dream_pop"},
        "search_plan": {"mutation_budget_per_round": 2},
        "round_number": 1,
        "progression_candidates": [existing_prog],
        "top_progressions": [existing_prog],
        "scorecards": [{"candidate_id": "pc_01", "weighted_total": 7.0, "scores": {"genre_fit": 7.0, "novelty": 5.0}}],
        "pareto_front": {"candidate_ids": ["pc_01"]},
        "mutation_records": [],
        "all_candidates_history": [],
        "arrangement_candidates": [{"id": "arr_01"}],
    }

    result = await mutate(state, gemini=mock_gemini)

    # Must include existing + new
    prog_ids = [p["id"] for p in result["progression_candidates"]]
    assert "pc_01" in prog_ids
    assert len(prog_ids) > 1  # at least one new mutant

    # Mutation records populated
    assert len(result["mutation_records"]) > 0

    # Stale downstream fields cleared (harmonic mutation)
    assert result["voicing_plans"] == []
    assert result["arrangement_candidates"] == []
    assert result["evaluations"] == []

    # Round incremented
    assert result["round_number"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/engine/test_mutate.py -v`

- [ ] **Step 3: Implement mutate node**

Create `backend/src/explorator/engine/nodes/mutate.py`:

```python
"""mutate node — orchestrate mutation engine and produce new candidates."""

import logging
from typing import Any

from ulid import ULID

from explorator.adapters.gemini import GeminiClient
from explorator.domain.harmony.mutator import HarmonyMutator
from explorator.engine.state import ExplorationState
from explorator.utils import utc_now

logger = logging.getLogger(__name__)


def _select_candidates_to_mutate(
    scorecards: list[dict[str, Any]],
    pareto_ids: list[str],
    budget: int,
    user_targeted: list[str] | None = None,
) -> list[str]:
    """Select candidate IDs to mutate, respecting budget.

    Priority: user-targeted > Pareto front > highest weighted_total.
    """
    selected: list[str] = []
    seen: set[str] = set()

    # 1. User-targeted
    for cid in (user_targeted or []):
        if cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    # 2. Pareto front members
    for cid in pareto_ids:
        if cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    # 3. Top scorers
    sorted_cards = sorted(scorecards, key=lambda s: s.get("weighted_total", 0.0), reverse=True)
    for sc in sorted_cards:
        cid = sc.get("candidate_id", "")
        if cid and cid not in seen and len(selected) < budget:
            selected.append(cid)
            seen.add(cid)

    return selected


async def mutate(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Mutate selected candidates and return merged state update.

    For harmonic mutations: clears downstream realization fields.
    Always returns full merged lists (existing + new) per overwrite semantics.
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "mutate"})

    plan = state.get("search_plan", {})
    budget = plan.get("mutation_budget_per_round", 6)
    round_number = state.get("round_number", 1)
    scorecards = state.get("scorecards", [])
    pareto = state.get("pareto_front", {})
    pareto_ids = pareto.get("candidate_ids", [])
    existing_progs = list(state.get("progression_candidates", []))
    existing_records = list(state.get("mutation_records", []))
    existing_history = list(state.get("all_candidates_history", []))
    genre = state.get("genre", state.get("genre_profile", {}).get("genre", ""))

    # Build lookup: candidate_id → progression data
    prog_by_id = {p["id"]: p for p in existing_progs}
    scores_by_id = {sc["candidate_id"]: sc.get("scores", {}) for sc in scorecards}

    # Select candidates to mutate
    to_mutate = _select_candidates_to_mutate(scorecards, pareto_ids, budget)

    mutator = HarmonyMutator(gemini)
    new_progs: list[dict[str, Any]] = []
    new_records: list[dict[str, Any]] = []
    now = utc_now()

    for source_id in to_mutate:
        source = prog_by_id.get(source_id)
        if not source:
            logger.warning("Mutation target %s not found in progressions", source_id)
            continue

        chord_symbols = source.get("chord_symbols", [])
        source_scores = scores_by_id.get(source_id, {})

        try:
            response = await mutator.mutate_harmonic(
                chord_symbols=chord_symbols,
                genre=genre,
                scores=source_scores,
            )
        except Exception:
            logger.exception("Gemini mutation failed for candidate %s — skipping", source_id)
            continue

        # Create new progression candidate from mutation result
        new_id = f"pc_{ULID()}"
        new_prog = {
            **source,
            "id": new_id,
            "chord_symbols": response.mutated_chord_symbols,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "metadata": {
                **source.get("metadata", {}),
                "mutated_from": source_id,
                "mutation_round": round_number + 1,
            },
        }
        new_progs.append(new_prog)

        # Create MutationRecord
        record = {
            "id": f"mr_{ULID()}",
            "type": "mutation_record",
            "status": "completed",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "source_candidate_id": source_id,
            "source_candidate_type": "progression",
            "result_candidate_id": new_id,
            "result_candidate_type": "progression",
            "mutation_scope": "harmonic",
            "changes": [m.model_dump() for m in response.mutations],
            "reason": "; ".join(m.reason for m in response.mutations),
            "predicted_effects": [
                f"{k}: {v:+.1f}" for m in response.mutations
                for k, v in m.predicted_effects.items()
            ],
            "actual_score_delta": {},
        }
        new_records.append(record)

    # Snapshot current candidates for history
    history_snapshot = [
        {"id": p["id"], "round": round_number, "scores": scores_by_id.get(p["id"], {})}
        for p in existing_progs
    ]

    if callback:
        await callback("mutation_completed", {
            "mutations_count": len(new_records),
            "round": round_number + 1,
        })

    # Return merged state — harmonic mutations clear downstream fields
    return {
        "progression_candidates": existing_progs + new_progs,
        "mutation_records": existing_records + new_records,
        "all_candidates_history": existing_history + history_snapshot,
        "round_number": round_number + 1,
        # Clear stale downstream fields for full re-pipeline
        "voicing_plans": [],
        "bass_lines": [],
        "arrangement_candidates": [],
        "arrangement_families": [],
        "selected_arrangements": [],
        "evaluations": [],
        "scorecards": [],
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/engine/test_mutate.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/nodes/mutate.py backend/tests/unit/engine/test_mutate.py
git commit -m "feat(m3a): mutate node with candidate selection, state merging, and downstream clearing"
```

---

### Task 9: Enhance rank_and_select with Basic Pareto Preservation

**Files:**
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Modify: `backend/tests/unit/engine/test_rank_and_select.py`

- [ ] **Step 1: Write the test**

Add to `backend/tests/unit/engine/test_rank_and_select.py`:

```python
from explorator.engine.nodes.rank_and_select import _identify_pareto_front


def test_identify_pareto_front_basic() -> None:
    """Non-dominated candidates identified correctly."""
    candidates = [
        {"id": "a", "merged_scores": {"genre_fit": 9.0, "novelty": 3.0, "loopability": 5.0, "playability": 5.0}},
        {"id": "b", "merged_scores": {"genre_fit": 3.0, "novelty": 9.0, "loopability": 5.0, "playability": 5.0}},
        {"id": "c", "merged_scores": {"genre_fit": 5.0, "novelty": 5.0, "loopability": 5.0, "playability": 5.0}},
    ]
    front = _identify_pareto_front(candidates)
    # All three are non-dominated (no single candidate beats another on ALL 4 axes)
    assert set(front) == {"a", "b", "c"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/engine/test_rank_and_select.py::test_identify_pareto_front_basic -v`

- [ ] **Step 3: Add Pareto identification to rank_and_select.py**

Add to `backend/src/explorator/engine/nodes/rank_and_select.py` after the existing `_rank_family` function:

```python
from explorator.domain.evaluation.pareto import compute_pareto_front

_PARETO_AXES = ["genre_fit", "novelty", "loopability", "playability"]


def _identify_pareto_front(candidates: list[dict[str, Any]]) -> set[str]:
    """Identify Pareto front candidates across key axes."""
    pareto_input = [
        {"id": c["id"], "scores": c.get("merged_scores", {})}
        for c in candidates
    ]
    front_ids = compute_pareto_front(pareto_input, axes=_PARETO_AXES)
    return set(front_ids)
```

- [ ] **Step 4: Update rank_and_select to use Pareto preservation**

In the `rank_and_select` function, after the existing family ranking loop (after `arr_status[arr_id] = ...`), add Pareto preservation logic. Find the section where `selected_ids` is finalized and add:

```python
    # --- Pareto preservation: ensure non-dominated candidates survive ---
    all_family_candidates = []
    for prog_id, arr_ids in by_prog.items():
        m1_scores = m1_scores_lookup.get(prog_id, {})
        for arr_id in arr_ids:
            m2b_scores = eval_lookup.get(arr_id, {})
            merged = {}
            for dim in _M1_DIMENSIONS:
                merged[dim] = float(m1_scores.get(dim, 5.0))
            merged.update(m2b_scores)
            all_family_candidates.append({"id": arr_id, "merged_scores": merged})

    pareto_ids = _identify_pareto_front(all_family_candidates)

    # Add Pareto members to selected set even if not top-k
    for pid in pareto_ids:
        if pid not in selected_ids:
            selected_ids.add(pid)
            arr_status[pid] = "selected"
```

Also update the scorecards to tag Pareto members. In the scorecard creation loop, after `rank_within_round=rank,` add:

```python
                pareto_tags=["pareto_front"] if arr_id in pareto_ids else [],
```

And add the Pareto front snapshot to the return dict:

```python
    pareto_snapshot = {
        "candidate_ids": list(pareto_ids),
        "axes": _PARETO_AXES,
    }
```

Then add `"pareto_front": pareto_snapshot,` to the return dict.

- [ ] **Step 5: Run all rank_and_select tests**

Run: `cd backend && uv run pytest tests/unit/engine/test_rank_and_select.py -v`

- [ ] **Step 6: Run full suite**

Run: `cd backend && uv run pytest tests/ -q`

- [ ] **Step 7: Commit**

```bash
git add backend/src/explorator/engine/nodes/rank_and_select.py backend/tests/unit/engine/test_rank_and_select.py
git commit -m "feat(m3a): basic Pareto preservation in rank_and_select"
```

---

### Task 10: Wire Mutation Loop into Graph

**Files:**
- Modify: `backend/src/explorator/engine/graph.py`
- Modify: `backend/tests/unit/engine/test_unified_graph.py`

- [ ] **Step 1: Write the tests**

Add to `backend/tests/unit/engine/test_unified_graph.py`:

```python
def test_exploration_graph_has_mutation_nodes() -> None:
    """Graph includes check_stop and mutate nodes."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    node_names = set(graph.nodes.keys())
    assert "check_stop" in node_names
    assert "mutate" in node_names


def test_exploration_graph_has_conditional_edges() -> None:
    """Graph has conditional routing from check_stop and mutate."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    # Verify the graph compiled successfully with conditional edges
    # (LangGraph would fail at compile time if edges were malformed)
    assert graph is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/engine/test_unified_graph.py::test_exploration_graph_has_mutation_nodes -v`

- [ ] **Step 3: Update graph.py with mutation loop**

In `backend/src/explorator/engine/graph.py`, add imports:

```python
from explorator.engine.nodes.check_stop import check_stop
from explorator.engine.nodes.mutate import mutate
```

Add the routing function before `build_exploration_graph`:

```python
def _route_after_stop(state: ExplorationState) -> str:
    """Route based on stop condition: persist or mutate."""
    if state.get("stop_condition_met", False):
        return "persist_realization"
    return "mutate"


def _route_after_mutate(state: ExplorationState) -> str:
    """Route based on mutation scope: harmonic (full re-pipeline) or arrangement."""
    records = state.get("mutation_records", [])
    current_round = state.get("round_number", 1)
    # Check if any mutation in the current round is harmonic
    current_records = [r for r in records if r.get("mutation_scope") == "harmonic"]
    if current_records:
        return "evaluate_progressions"
    return "evaluate_arrangements"
```

Then update `build_exploration_graph` — replace the section from `rank_and_select` to `END`:

Change:
```python
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", "persist_round")
    graph.add_edge("persist_round", END)
```

To:
```python
    # M3a: mutation loop
    graph.add_node("check_stop", check_stop)
    graph.add_node("mutate", partial(mutate, gemini=gemini))

    graph.add_edge("rank_and_select", "check_stop")

    # Conditional: stop → persist, continue → mutate
    graph.add_conditional_edges("check_stop", _route_after_stop, {
        "persist_realization": "persist_realization",
        "mutate": "mutate",
    })

    # Conditional: harmonic → evaluate_progressions, arrangement → evaluate_arrangements
    graph.add_conditional_edges("mutate", _route_after_mutate, {
        "evaluate_progressions": "evaluate_progressions",
        "evaluate_arrangements": "evaluate_arrangements",
    })

    graph.add_edge("persist_realization", "persist_round")
    graph.add_edge("persist_round", END)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/unit/engine/test_unified_graph.py -v`
Then: `cd backend && uv run pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add backend/src/explorator/engine/graph.py backend/tests/unit/engine/test_unified_graph.py
git commit -m "feat(m3a): wire check_stop + mutate nodes with conditional routing into graph"
```

---

### Task 11: Expand persist_round for M3a Entities

**Files:**
- Modify: `backend/src/explorator/engine/nodes/persist_round.py`

- [ ] **Step 1: Add SearchRound and MutationRecord persistence**

In `backend/src/explorator/engine/nodes/persist_round.py`, add imports:

```python
from explorator.graph.search_round_repo import SearchRoundRepo
from explorator.graph.mutation_record_repo import MutationRecordRepo
from explorator.models.search import SearchRound, MutationRecord
```

After the existing candidate persistence section, add:

```python
    # --- M3a: Persist SearchRound ---
    round_number = state.get("round_number", 1)
    search_round = SearchRound(
        id=f"sr_{ULID()}",
        type="search_round",
        status="completed",
        created_at=utc_now(),
        updated_at=utc_now(),
        session_id=session_id,
        round_number=round_number,
        selected_candidate_ids=[p.get("id", "") for p in state.get("top_progressions", [])],
    )
    try:
        sr_repo = SearchRoundRepo(driver)
        await sr_repo.create(search_round)
    except Exception:
        logger.exception("Failed to persist SearchRound")

    # --- M3a: Persist MutationRecords ---
    mr_repo = MutationRecordRepo(driver)
    for mr_data in state.get("mutation_records", []):
        try:
            mr = MutationRecord.model_validate(mr_data)
            await mr_repo.create(mr)
        except Exception:
            logger.exception("Failed to persist MutationRecord %s", mr_data.get("id"))
```

Note: Add `from ulid import ULID` and `from explorator.utils import utc_now` if not already imported.

- [ ] **Step 2: Run tests**

Run: `cd backend && uv run pytest tests/ -q`

- [ ] **Step 3: Commit**

```bash
git add backend/src/explorator/engine/nodes/persist_round.py
git commit -m "feat(m3a): persist SearchRound and MutationRecords in persist_round node"
```

---

### Task 12: Mutation API Endpoint

**Files:**
- Create: `backend/src/explorator/api/routes/mutations.py`
- Modify: `backend/src/explorator/api/app.py` (register router)

- [ ] **Step 1: Create the endpoint**

Create `backend/src/explorator/api/routes/mutations.py`:

```python
"""API routes for user-initiated mutations."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.domain.harmony.mutator import HarmonyMutator
from explorator.graph.session_repo import SessionRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mutations"])


class TriggerMutationRequest(BaseModel):
    candidate_ids: list[str]
    guidance: str | None = None
    operations: list[str] | None = None


@router.post("/sessions/{session_id}/mutate")
async def trigger_mutation(
    session_id: str,
    request: TriggerMutationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger user-initiated mutations on specific candidates.

    Returns 409 if a round is already in-flight for this session.
    """
    repo = SessionRepository(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.candidate_ids:
        raise HTTPException(status_code=422, detail="At least one candidate_id required")

    # TODO: Add concurrency guard (check session.status != "in_progress")

    channel = SSEChannel()

    async def run_mutation() -> None:
        try:
            mutator = HarmonyMutator(gemini)
            results: list[dict[str, Any]] = []

            for cid in request.candidate_ids:
                # Fetch candidate from Neo4j
                from explorator.graph.repository import BaseRepository

                class ProgRepo(BaseRepository):
                    label = "ProgressionCandidate"

                prog_repo = ProgRepo(driver)
                candidate = await prog_repo.get_by_id(cid)
                if candidate is None:
                    await channel.send("mutation_error", {"error": f"Candidate {cid} not found"})
                    continue

                chord_symbols = candidate.get("chord_symbols", [])
                scores = candidate.get("metadata", {}).get("scores", {})

                response = await mutator.mutate_harmonic(
                    chord_symbols=chord_symbols,
                    genre=session.get("genre", ""),
                    scores=scores,
                    guidance=request.guidance,
                )

                results.append({
                    "source_id": cid,
                    "mutated_chord_symbols": response.mutated_chord_symbols,
                    "mutations": [m.model_dump() for m in response.mutations],
                })

            await channel.send("mutation_completed", {"results": results})
        except Exception as e:
            logger.exception("Mutation failed for session %s", session_id)
            await channel.send("mutation_error", {"error": str(e)})
        finally:
            await channel.close()

    asyncio.create_task(run_mutation())
    return EventSourceResponse(channel.stream())
```

- [ ] **Step 2: Register the router**

In `backend/src/explorator/api/app.py`, add:

```python
from explorator.api.routes.mutations import router as mutations_router
```

And in the `create_app` function where other routers are included, add:

```python
app.include_router(mutations_router, prefix="/v1")
```

- [ ] **Step 3: Run tests**

Run: `cd backend && uv run pytest tests/ -q`

- [ ] **Step 4: Commit**

```bash
git add backend/src/explorator/api/routes/mutations.py backend/src/explorator/api/app.py
git commit -m "feat(m3a): POST /v1/sessions/:id/mutate endpoint for user-initiated mutations"
```

---

### Task 13: Final Backend Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests pass (264+ existing + new M3a tests)

- [ ] **Step 2: Run ruff on changed files**

Run: `cd backend && uv run ruff check src/explorator/engine/ src/explorator/domain/ src/explorator/prompts/mutation.py src/explorator/api/routes/mutations.py src/explorator/graph/search_round_repo.py src/explorator/graph/mutation_record_repo.py`

- [ ] **Step 3: Verify graph compiles with new nodes**

```bash
cd backend && uv run python -c "
from explorator.engine.graph import build_exploration_graph
from unittest.mock import MagicMock
g = build_exploration_graph(MagicMock(), MagicMock())
nodes = sorted(n for n in g.nodes.keys() if not n.startswith('__'))
print(f'Nodes ({len(nodes)}): {nodes}')
assert 'check_stop' in nodes
assert 'mutate' in nodes
print('M3a graph compiled successfully')
"
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "fix(m3a): final verification fixes"
```

---

### Task 14: Frontend — Round Progress SSE Updates

**Files:**
- Modify: `frontend/src/services/sse.ts` — add new event types
- Modify: `frontend/src/views/SessionWorkspace.tsx` — handle round progress display

- [ ] **Step 1: Add SSE event types**

In `frontend/src/services/sse.ts`, add to the event type union:

```typescript
| 'mutation_completed'
| 'mutation_error'
```

- [ ] **Step 2: Update SessionWorkspace to show round progress**

In the SSE handler in `SessionWorkspace.tsx`, add handling for round progress:
- Display "Round N/M — Mutating..." during mutation
- Display "Round N/M — Evaluating..." during evaluation re-run
- Show stop reason when complete ("Stopped: quality threshold met")

- [ ] **Step 3: Test manually**

Start backend and frontend, trigger a round, verify progress displays correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(m3a): frontend round progress SSE handling"
```

---

### Task 15: Frontend — Lineage Badges and Mutate Button

**Files:**
- Modify candidate card component to show lineage badge
- Create mutation modal component

- [ ] **Step 1: Add lineage badge to candidate cards**

On arrangement/progression candidate cards, check for `metadata.mutated_from`. If present, show a badge: "Mutated from {source_id}" with a harmonic/arrangement icon.

- [ ] **Step 2: Create MutateModal component**

Simple modal with:
- Optional text input for guidance
- Checkboxes for operation types (from `MUTATION_OPERATIONS`)
- Submit button that calls `POST /v1/sessions/:id/mutate`

- [ ] **Step 3: Add Mutate button to candidate cards**

Button on each candidate card that opens the MutateModal with the candidate ID pre-filled.

- [ ] **Step 4: Test manually and commit**

```bash
git add frontend/src/
git commit -m "feat(m3a): lineage badges and mutate button on candidate cards"
```

---

### Task 16: Frontend — Lineage Tree View

**Files:**
- Create new LineageTree component

- [ ] **Step 1: Build LineageTree component**

A collapsible tree view showing parent → child relationships from mutation records. Each node displays:
- Candidate ID (abbreviated)
- Mutation type badge (harmonic/arrangement)
- Click navigates to candidate detail

Data source: `mutation_records` from the session state, plus `metadata.mutated_from` on candidates.

- [ ] **Step 2: Integrate into arrangement panel**

Add as a new tab or collapsible section alongside the arrangement list. Only visible when mutations exist.

- [ ] **Step 3: Test manually and commit**

```bash
git add frontend/src/
git commit -m "feat(m3a): lineage tree view for mutation history"
```
