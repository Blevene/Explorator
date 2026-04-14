# Post-Mutation Realization Fix

**Version**: v1.0
**Date**: 2026-04-14
**Status**: Approved
**Branch**: `feat/m4b-explanation-comparison-provenance` (current working branch)

---

## 1. Problem

The user-initiated mutation endpoint (`POST /sessions/{id}/mutate`) creates a new `ProgressionCandidate` in Neo4j but never runs the realization pipeline. The mutated candidate has chord symbols but no voicing plans, bass lines, or arrangements. When the user navigates to the arrangement view for the mutated candidate, nothing is there.

The LangGraph exploration loop handles realization automatically because `mutate` is a graph node with edges routing back through the realization pipeline. The user-initiated endpoint bypasses the graph — it's a standalone API call.

## 2. Fix

After the mutation endpoint persists the new `ProgressionCandidate`, invoke the realization pipeline for that candidate. The pipeline runs the same M2 nodes as the full graph: `load_context` → `plan_voicings` → `generate_bass` → `assemble_arrangements` → `evaluate_arrangements` → `rank_and_select` → `persist_realization` → `persist_round`.

## 3. Design

### 3.1 New realization graph — `engine/graph.py`

Add `build_realization_graph(gemini, driver)` — a compiled LangGraph that starts at `load_context` and runs through the M2 pipeline + persist. Same nodes as the existing graph, different entry point and no M1 nodes (parse_intent, load_genre, generate, evaluate_progressions, select_top_progressions) or mutation loop (check_stop, mutate).

```
load_context → plan_voicings → generate_bass → assemble_arrangements
    → evaluate_arrangements → rank_and_select → persist_realization → persist_round → END
```

This reuses all existing node functions — no new domain logic.

### 3.2 Mutation endpoint change — `api/routes/mutations.py`

After persisting the mutated candidate and sending the `mutation_completed` SSE event, the endpoint:

1. Loads session context from Neo4j: `session_id`, `genre`, `creative_brief`, `genre_profile`, `search_plan`.
2. Builds initial state for the realization graph:
   - `session_id`, `prompt`, `genre`
   - `creative_brief`, `genre_profile`, `search_plan` — loaded from Neo4j via existing repos
   - `progression_candidates`: `[new_mutated_candidate_data]` (single-element list)
   - `top_progressions`: same list (so `rank_and_select` finds M1 scores in metadata)
   - `provenance_events: []`
   - `round_number`: current round + 1
   - `on_progress`: the SSE channel callback (so the user sees realization progress)
3. Invokes `realization_graph.ainvoke(initial_state)`.
4. Sends `round_complete` SSE event when done.

The SSE stream now shows: mutation progress → realization progress (plan_voicings, generate_bass, etc.) → round_complete. One continuous stream.

### 3.3 Session context loading

The mutation endpoint needs to load session data that the realization graph expects. Create a helper function `load_session_context(session_id, driver)` that returns the state dict with:
- `genre_profile` (from GenreProfile node)
- `creative_brief` (from CreativeBrief node)
- `search_plan` (from SearchPlan node, or defaults)

This helper can live in `api/routes/mutations.py` or be extracted to a shared utility if other endpoints need it later.

### 3.4 What does NOT change

- The full `/rounds` endpoint — unchanged
- The LangGraph mutation loop (check_stop → mutate → evaluate) — unchanged
- All existing graph nodes — unchanged, they already handle single-candidate lists
- The frontend — the SSE event handlers already process `node_started`/`node_completed` events from realization nodes. The only new behavior is that these events now appear after `mutation_completed`.

## 4. Error Handling

| Failure | Handling |
|---|---|
| Realization graph fails | Log error, send `realization_error` SSE event with message. The mutated candidate still exists in Neo4j (harmonic mutation succeeded) but has no arrangements. |
| Session context not found | Log error, send `realization_error`. Should not happen since the session was just verified. |
| Individual node failure (e.g., Gemini timeout in plan_voicings) | The existing node-level error handling applies. Partial results may be persisted. |

## 5. Testing

- **Unit test**: Mock the realization graph, verify the mutation endpoint calls it with correct initial state after mutation.
- **Integration test**: Full flow — mutate a candidate, verify arrangements exist in Neo4j for the new candidate.
- **E2E test**: Click Mutate, wait for completion, verify the mutated candidate shows arrangements in the arrangement view.
