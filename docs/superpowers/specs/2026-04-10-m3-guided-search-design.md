# M3 — Guided Search: Design Specification

**Version**: v1.0
**Date**: 2026-04-10
**Status**: Approved
**Branch**: `feat/m3-guided-search` (to be created)

---

## 1. Overview

M3 completes the iterative exploration loop. Users can mutate candidates, provide natural language feedback to steer scoring, and receive diversity-aware finalist selections. The milestone is decomposed into four sub-milestones plus a preparatory step.

### Sub-Milestone Breakdown

| Sub-milestone | Depends On | Deliverable |
|---|---|---|
| **M3-prep** | M2 complete | Unified graph & state |
| **M3a** | M3-prep | Mutation loop, stop conditions, lineage UI |
| **M3b** | M3a | Feedback interpretation, weight reweighting, chat sidebar |
| **M3c** | M3a | Pareto ranking, diversity penalties, finalist roles |
| **M3d** | M3a-c | Full frontend design audit & iteration |

M3b and M3c are independent of each other and can be built in parallel after M3a. M3d waits for all three.

---

## 2. M3-prep — Unified Graph & State

### Problem

M1 and M2 run as separate pipelines with separate state types (`ExplorationState` and `RealizationState`). M3's mutation loop requires a single graph so mutations can route to the correct re-entry point.

### Unified ExplorationState

Merge `RealizationState` fields into `ExplorationState`:

```python
class ExplorationState(TypedDict, total=False):
    # --- Session context ---
    session_id: str
    prompt: str
    genre: str
    generation_mode: str

    # --- Parsed intent ---
    creative_brief: dict[str, Any]

    # --- Genre data ---
    genre_profile: dict[str, Any]
    harmonic_grammar: dict[str, Any]
    genre_rules: list[dict[str, Any]]

    # --- Generation outputs ---
    progression_candidates: list[dict[str, Any]]
    top_progressions: list[dict[str, Any]]

    # --- Evaluation outputs ---
    evaluations: list[dict[str, Any]]
    scorecards: list[dict[str, Any]]

    # --- Realization (from RealizationState) ---
    progression_candidate_ids: list[str]
    voicing_strategies: list[dict[str, Any]]
    voicing_plans: list[dict[str, Any]]
    bass_lines: list[dict[str, Any]]
    arrangement_candidates: list[dict[str, Any]]
    arrangement_families: list[dict[str, Any]]
    selected_arrangements: list[dict[str, Any]]

    # --- Search control ---
    round_number: int
    n_candidates: int
    k_selection: int

    # --- Progress callback ---
    on_progress: Any
```

### Unified Graph — `build_exploration_graph()`

Replaces `build_m1_graph()`. Linear flow wiring all 13 existing nodes:

```
parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble_arrangements → evaluate_arrangements
  → rank_and_select → persist_round → END
```

### Node Signature Updates

M2 nodes currently take `RealizationState`. Update all to accept `ExplorationState`. Field names are identical — node logic does not change, only the type annotation.

### API Compatibility

- `POST /v1/sessions/:id/rounds` runs the full unified pipeline
- `POST /v1/sessions/:id/realization-rounds` is kept for independent realization (realize a different set of progressions without regenerating)

### Migration

- `RealizationState` becomes a temporary re-export alias of `ExplorationState`, then is removed once all nodes are updated
- `build_m1_graph()` is replaced, not kept alongside
- All existing tests updated to use unified state

---

## 3. M3a — Mutation Loop

### 3.1 Graph Topology

Three new nodes and conditional branching added to the unified graph:

```
parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble_arrangements → evaluate_arrangements
  → rank_and_select → check_stop
      → [stop_met=true]  → persist_round → END
      → [stop_met=false] → mutate → route_mutation
          → [scope=harmonic]     → evaluate_progressions  (full re-pipeline)
          → [scope=arrangement]  → evaluate_arrangements  (skip regeneration)
```

`route_mutation` is a conditional edge function (not a full node). It reads the latest mutation records from state and determines the route: if ANY mutation in the round has `mutation_scope == "harmonic"`, the route is `"evaluate_progressions"` (full re-pipeline). Only if ALL mutations are arrangement-scoped does it route to `"evaluate_arrangements"`.

When harmonic mutations loop to `evaluate_progressions`, the full pipeline continues through realization. When arrangement mutations loop to `evaluate_arrangements`, only `evaluate_arrangements → rank_and_select → check_stop` runs.

`round_number` increments each time `check_stop` fires.

### 3.2 State Additions

```python
    # --- M3a: Search & Mutation ---
    search_plan: dict[str, Any]
    mutation_records: list[dict[str, Any]]
    stop_condition_met: bool
    stop_reason: str  # "quality" | "budget" | "diversity"
    pareto_front: dict[str, Any]
    all_candidates_history: list[dict[str, Any]]  # Cumulative across rounds
```

### 3.3 Mutation Engine — `domain/harmony/mutator.py`

**`HarmonyMutator` service** using Gemini Pro.

#### Mutation Vocabulary (Constrained Operations)

| Operation | Scope | Description |
|---|---|---|
| `substitute_chord` | harmonic | Replace one chord with a diatonic/chromatic substitute |
| `reharmonize_cadence` | harmonic | Change the cadence type (e.g., V-I → bVII-I) |
| `modal_interchange` | harmonic | Borrow chord from parallel mode |
| `alter_density` | harmonic | Add or remove passing chords |
| `swap_voicing_type` | arrangement | Change voicing strategy (open → drop-2, etc.) |
| `swap_bass_mode` | arrangement | Change bass pattern (supportive → syncopated, etc.) |
| `shift_register` | arrangement | Transpose voicing register up/down an octave |
| `experimental` | either | Free-form Gemini proposal with explanation |

#### Gemini Pro Prompt

- **Input**: candidate progression/arrangement, genre profile, current scores, optional user guidance text
- **Output**: structured JSON — selected operation(s) from vocabulary, parameters, reason, predicted score effects
- For `experimental`: free-form description mapped to `MutationChange`

#### Mutation Budget & Selection

`SearchPlan.mutation_budget_per_round` (default 6) limits mutations per round. Candidates to mutate are selected by priority:

1. User-targeted candidates (from manual mutation requests)
2. Pareto front members (preserved diversity)
3. Highest `weighted_total` candidates not on Pareto front

### 3.4 `check_stop` Node

Deterministic logic, no Gemini call. Checks three conditions (condition 4 added in M3b):

1. **Quality threshold**: Top candidate `weighted_total >= target_score` (default 8.5, configurable via `SearchPlan.stop_conditions`)
2. **Diversity sufficient**: ≥3 candidates on Pareto front with pairwise chord edit distance > 2
3. **Budget exhausted**: `round_number >= max_rounds` (default 4)

Stop on ANY condition met.

### 3.5 Basic Pareto Preservation in `rank_and_select`

Enhancement to existing node for M3a:

1. After computing weighted totals, identify non-dominated candidates (no other candidate scores strictly higher on all of: genre_fit, novelty, loopability, playability)
2. Tag with `pareto_tags: ["pareto_front"]` on `AggregateScorecard`
3. Selection = top-k by weighted score UNION Pareto front members
4. Build `ParetoFrontSnapshot` and write to state

This prevents the auto-loop from killing diverse candidates.

### 3.6 `mutate` Node

1. Read `search_plan.mutation_budget_per_round`
2. Select candidates to mutate (priority order above)
3. For each, call `HarmonyMutator.mutate()` (Gemini Pro)
4. Create new candidate entities with new IDs, linked via `MutationRecord`
5. Add new candidates + mutation records to state
6. Determine overall mutation scope — if ANY mutation is harmonic, route is harmonic

### 3.7 User-Initiated Mutations

**API**: `POST /v1/sessions/:id/mutate`

```json
{
    "candidate_ids": ["arr_01ABC"],
    "guidance": "make the bass more syncopated",
    "operations": ["swap_bass_mode"]
}
```

`operations` is optional — if omitted, Gemini decides. Triggers a single mutation round outside the auto-loop. Response streams progress via SSE. Result feeds back into the session's candidate pool.

### 3.8 Frontend

- **Round progress**: Extend SSE progress bar to show "Round 2/4 — Mutating..." / "Round 3/4 — Evaluating..."
- **Lineage badges**: On candidate cards, "Mutated from C-3" badge with mutation type icon (harmonic vs arrangement)
- **Lineage tree**: Collapsible tree view showing parent → child relationships. Click a node to navigate to that candidate's detail. New tab/panel alongside the arrangement list.
- **Mutate button**: On candidate cards, opens modal with optional guidance text and operation checkboxes

---

## 4. M3b — Feedback & Reweighting

### 4.1 Feedback Flow

```
User types feedback → POST /v1/candidates/:id/feedback
  → Gemini Flash interprets → two outputs:
      1. interpreted_adjustments (semantic map for explainability)
      2. adjusted_weights (numerical deltas for ObjectiveWeights)
  → Persist UserFeedbackEvent to Neo4j
  → Apply deltas to session's ObjectiveWeights, renormalize
  → Next round uses adjusted weights
```

### 4.2 `load_memory` Node

Deterministic data fetch, no Gemini call. Inserted after `load_genre`, before `generate`:

```
parse_intent → load_genre → load_memory → generate → ...
```

Loads from Neo4j into state:
- `feedback_history`: All `UserFeedbackEvent` for this session
- `objective_weights`: Current `ObjectiveWeights` (default or feedback-adjusted)
- `user_preference_profile`: If one exists (optional, can be empty)

These feed into `generate` (Gemini knows user preferences) and `rank_and_select` (scoring uses adjusted weights).

### 4.3 Feedback Interpretation — `domain/intent/feedback.py`

**`FeedbackInterpreter` service** using Gemini Flash.

**Input**: feedback text, current `ObjectiveWeights`, candidate scores/metadata, genre profile

**Output**:
```python
class FeedbackInterpretation(BaseModel):
    interpreted_adjustments: dict[str, Any]
    # e.g. {"reduce_bass_motion": true, "prefer_open_voicings": true}

    weight_deltas: dict[str, float]
    # e.g. {"novelty": +0.04, "playability": -0.02, "loopability": -0.02}
```

**Reweighting logic**:
1. Apply deltas: `new_weight[dim] = current_weight[dim] + delta[dim]`
2. Clamp all weights to `[0.02, 0.50]` — no dimension goes to zero or dominates
3. Renormalize to sum 1.0
4. Persist new `ObjectiveWeights` with `profile_name: "session_{id}_round_{n}"`

### 4.4 State Additions

```python
    # --- M3b: Feedback & Memory ---
    feedback_history: list[dict[str, Any]]
    objective_weights: dict[str, Any]
    user_preference_profile: dict[str, Any]
```

`rank_and_select` switches from `DEFAULT_WEIGHTS` to `state["objective_weights"]` when present.

### 4.5 Stop Condition 4: User Satisfaction

Added to `check_stop` in M3b:

Gemini Flash tags feedback with `{"satisfaction": "positive"}` in `interpreted_adjustments` when the user expresses satisfaction ("this is great", "love this one", "perfect"). `check_stop` looks for positive satisfaction signals in recent feedback for current-round candidates.

### 4.6 API

**`POST /v1/candidates/:id/feedback`**

Request:
```json
{
    "content": "bass is too busy, voicings should be more open",
    "feedback_type": "text_reaction"
}
```

Response:
```json
{
    "id": "fb_01ABC",
    "interpreted_adjustments": {
        "reduce_bass_motion": true,
        "prefer_open_voicings": true
    },
    "adjusted_weights": {
        "playability": 0.14,
        "voice_leading": 0.17,
        "novelty": 0.09
    }
}
```

### 4.7 Frontend — Feedback Sidebar

- **Chat-style sidebar** on the right of the arrangement detail view
- User types feedback, sees interpretation result ("Understood: reduce bass motion, prefer open voicings")
- **Weight visualization**: Small horizontal bar chart showing current dimension weights with deltas highlighted after feedback
- Feedback history persists per session — scrollable thread

---

## 5. M3c — Pareto Ranking & Finalists

### 5.1 Full Pareto Front Construction

New function in `domain/evaluation/ranking.py`: `compute_pareto_front()`

**Axes**: genre_fit, novelty, loopability, playability

**Algorithm**: Non-dominated sort. Candidate A dominates B if A ≥ B on all axes and strictly > on at least one. O(n²) pairwise comparison — sufficient for our candidate pool sizes (dozens, not thousands).

**Output**: `ParetoFrontSnapshot` with candidate IDs and axes used.

### 5.2 Diversity Penalties

Two distance metrics:

1. **Chord edit distance**: Count of differing chord symbols between two progressions (position-wise). Distance ≤ 2 = near-duplicates.
2. **Score-space Euclidean distance**: `sqrt(sum((scores_a[dim] - scores_b[dim])²))`. Distance < 0.5 = similar quality profile.

**Penalty logic**: Among top-N candidates, if two have chord edit distance ≤ 2 AND score-space distance < 0.5, the lower-ranked one is demoted, opening a slot for a more diverse candidate.

`SearchPlan.diversity_target` (default 0.65) = minimum fraction of top-N that must be pairwise diverse.

### 5.3 Selection Roles

| Role | Criteria |
|---|---|
| **Safest** | Highest `weighted_total` where `genre_fit > 8.0` |
| **Best Loop** | Highest `loopability` score |
| **Most Experimental Viable** | Highest `novelty` where `weighted_total > 7.0` |

Stored in `FinalSelection.selection_roles` as `{"arr_01ABC": "safest", ...}`. A candidate can hold multiple roles. If no candidate qualifies for a role, that role is left empty with a note in `selection_notes`.

### 5.4 `rank_and_select` Final Form

By M3c, the node orchestrates sub-functions in `domain/evaluation/ranking.py`:

- `compute_pareto_front(candidates, axes) → ParetoFrontSnapshot`
- `apply_diversity_penalty(candidates, top_n, edit_dist_threshold, score_dist_threshold) → list`
- `assign_selection_roles(candidates, scorecards) → FinalSelection`

Evolution across milestones:

| Version | Behavior |
|---|---|
| M2 (current) | Weighted score, top-k per family, threshold gate |
| M3a | + basic Pareto preservation |
| M3c | + full Pareto front, diversity penalties, selection roles, configurable weights |

### 5.5 Persistence

- `FinalSelection` node in Neo4j with `SELECTS` edges to `ArrangementCandidate`, carrying a `role` property
- `ParetoFrontSnapshot` linked to `SearchRound` via `HAS_PARETO_FRONT`

### 5.6 Frontend — Finalist Panel

- **Finalist section** at the top of the arrangement list, visually distinct
- Each finalist card shows role badge ("Safest", "Best Loop", "Most Experimental")
- **Comparison view**: Side-by-side of up to 3 finalists showing 9-dimension score charts, chord symbols, mutation lineage
- Pareto front indicator on candidate cards

---

## 6. M3d — Frontend Design Review & Iteration

### 6.1 Scope

Holistic design pass over the entire frontend using the frontend-design skill. By M3d, the UI will have accumulated surfaces from M0 through M3c. This audit reviews it as a whole.

### 6.2 Review Concerns

1. **Information hierarchy**: Are finalists and round status prominent? Are secondary details (lineage tree, weight bars) appropriately tucked away?
2. **Layout coherence**: Does the split-panel pattern hold with the feedback sidebar, lineage tree, and finalist panel added?
3. **Workflow continuity**: Can a user smoothly flow from generating → reviewing → feedback → mutations → comparing finalists?
4. **Visual consistency**: Colors, spacing, typography, badge styles across all additions
5. **Progressive disclosure**: M3 features hidden until relevant (e.g., lineage tree only after mutations exist)

### 6.3 Process

1. Invoke frontend-design skill with full UI inventory
2. Audit current implementation against design principles
3. Produce prioritized refinement list
4. Implement iteratively with visual verification

### 6.4 Boundaries

M3d touches only frontend: React components, layouts, styles, Zustand store shape. No backend changes. Any backend needs discovered get filed for a future milestone.

---

## 7. Files to Create

| File | Sub-milestone | Purpose |
|---|---|---|
| `engine/nodes/load_memory.py` | M3b | Load feedback history + preferences into state |
| `engine/nodes/check_stop.py` | M3a | Evaluate stop conditions |
| `engine/nodes/mutate.py` | M3a | Orchestrate mutation engine |
| `domain/harmony/mutator.py` | M3a | Gemini Pro mutation service |
| `domain/intent/feedback.py` | M3b | Gemini Flash feedback interpretation |
| `domain/evaluation/pareto.py` | M3c | Pareto front + diversity functions |
| `graph/search_round_repo.py` | M3a | Neo4j CRUD for SearchRound |
| `graph/mutation_record_repo.py` | M3a | Neo4j CRUD for MutationRecord |
| `graph/feedback_repo.py` | M3b | Neo4j CRUD for UserFeedbackEvent |
| `graph/final_selection_repo.py` | M3c | Neo4j CRUD for FinalSelection |
| `api/routes/feedback.py` | M3b | POST /v1/candidates/:id/feedback |
| `api/routes/mutations.py` | M3a | POST /v1/sessions/:id/mutate |

## 8. Files to Modify

| File | Sub-milestone | Change |
|---|---|---|
| `engine/state.py` | M3-prep, M3a, M3b | Merge RealizationState, add M3 fields |
| `engine/graph.py` | M3-prep, M3a, M3b | Unified graph, conditional branching, load_memory node |
| `engine/nodes/rank_and_select.py` | M3a, M3c | Pareto preservation → full Pareto + diversity + roles |
| `engine/nodes/persist_round.py` | M3a, M3c | Persist MutationRecords, ParetoFrontSnapshot, FinalSelection |
| `domain/evaluation/ranking.py` | M3a, M3c | Pareto, diversity, weighted scoring functions |
| All M2 node files | M3-prep | RealizationState → ExplorationState signature |

## 9. Existing Model Stubs (No Changes Needed)

All M3 Pydantic models are already defined:
- `models/search.py`: SearchPlan, StopConditions, SearchRound, MutationRecord, MutationChange, ParetoFrontSnapshot, FinalSelection
- `models/memory.py`: UserPreferenceProfile, UserFeedbackEvent, PatternLibraryEntry (M5)
- `models/evaluation.py`: ObjectiveWeights, AggregateScorecard (has `pareto_tags` field)
- `graph/schema.py`: Neo4j constraints declared for all M3 node types
