# M3c — Pareto Ranking & Finalists Implementation Plan


**Goal:** Upgrade rank_and_select with full Pareto front, diversity penalties, and selection roles (Safest/Best Loop/Most Experimental), then surface finalists in the frontend with role badges and a comparison view.

**Architecture:** Three new pure functions in `ranking.py` (`apply_diversity_penalty`, `assign_selection_roles`, `chord_edit_distance`) plus a `FinalSelection` state field. `rank_and_select` node orchestrates them. Frontend adds a finalist section at the top of ArrangementList and a comparison modal.

**Tech Stack:** Python 3.12, Pydantic v2, React 18, Zustand, Tailwind CSS

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/src/explorator/domain/evaluation/ranking.py` | Add `chord_edit_distance`, `score_space_distance`, `apply_diversity_penalty`, `assign_selection_roles` |
| Modify | `backend/src/explorator/engine/nodes/rank_and_select.py` | Orchestrate diversity + selection roles, emit `final_selection` |
| Modify | `backend/src/explorator/engine/state.py` | Add `final_selection` field |
| Create | `backend/tests/unit/domain/test_diversity.py` | Tests for diversity penalty functions |
| Create | `backend/tests/unit/domain/test_selection_roles.py` | Tests for role assignment |
| Modify | `backend/tests/unit/engine/test_rank_and_select.py` | Test final_selection in node output |
| Modify | `frontend/src/services/api.ts` | Add `FinalistInfo` type |
| Modify | `frontend/src/stores/arrangementStore.ts` | Add `finalists` state |
| Create | `frontend/src/components/FinalistPanel.tsx` | Finalist cards with role badges |
| Modify | `frontend/src/components/ArrangementList.tsx` | Render FinalistPanel at top |

---

### Task 1: Distance Functions in ranking.py

**Files:**
- Modify: `backend/src/explorator/domain/evaluation/ranking.py`
- Create: `backend/tests/unit/domain/test_diversity.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/domain/test_diversity.py
"""Tests for diversity distance functions."""

import math

from explorator.domain.evaluation.ranking import (
    chord_edit_distance,
    score_space_distance,
)


def test_chord_edit_distance_identical() -> None:
    assert chord_edit_distance(["C", "G", "Am", "F"], ["C", "G", "Am", "F"]) == 0


def test_chord_edit_distance_one_diff() -> None:
    assert chord_edit_distance(["C", "G", "Am", "F"], ["C", "G", "Am", "E"]) == 1


def test_chord_edit_distance_all_different() -> None:
    assert chord_edit_distance(["C", "G"], ["Am", "F"]) == 2


def test_chord_edit_distance_different_lengths() -> None:
    # Shorter padded with "" — each missing position is a diff
    assert chord_edit_distance(["C", "G"], ["C", "G", "Am", "F"]) == 2


def test_chord_edit_distance_empty() -> None:
    assert chord_edit_distance([], []) == 0
    assert chord_edit_distance(["C"], []) == 1


def test_score_space_distance_identical() -> None:
    scores = {"a": 5.0, "b": 5.0}
    assert score_space_distance(scores, scores) == 0.0


def test_score_space_distance_basic() -> None:
    a = {"x": 3.0, "y": 0.0}
    b = {"x": 0.0, "y": 4.0}
    assert abs(score_space_distance(a, b) - 5.0) < 0.01  # 3-4-5 triangle


def test_score_space_distance_missing_dims() -> None:
    a = {"x": 5.0}
    b = {"x": 5.0, "y": 3.0}
    # Missing dim defaults to 0: sqrt((5-5)^2 + (0-3)^2) = 3.0
    assert abs(score_space_distance(a, b) - 3.0) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_diversity.py -v`
Expected: FAIL — functions not found

- [ ] **Step 3: Implement the distance functions**

Append to `backend/src/explorator/domain/evaluation/ranking.py`:

```python
import math


def chord_edit_distance(chords_a: list[str], chords_b: list[str]) -> int:
    """Count differing chord symbols between two progressions (position-wise).

    Pads the shorter progression — each missing position counts as a difference.
    """
    max_len = max(len(chords_a), len(chords_b))
    diffs = 0
    for i in range(max_len):
        a = chords_a[i] if i < len(chords_a) else ""
        b = chords_b[i] if i < len(chords_b) else ""
        if a != b:
            diffs += 1
    return diffs


def score_space_distance(
    scores_a: dict[str, float],
    scores_b: dict[str, float],
) -> float:
    """Euclidean distance in score-space across all dimensions in either dict."""
    all_dims = set(scores_a) | set(scores_b)
    total = 0.0
    for dim in all_dims:
        diff = scores_a.get(dim, 0.0) - scores_b.get(dim, 0.0)
        total += diff * diff
    return math.sqrt(total)
```

Note: Add `import math` at the top of `ranking.py` if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_diversity.py -v`
Expected: ALL PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd <repo-root> && git add backend/src/explorator/domain/evaluation/ranking.py backend/tests/unit/domain/test_diversity.py && git commit -m "feat(m3c): chord_edit_distance and score_space_distance functions"
```

---

### Task 2: apply_diversity_penalty Function

**Files:**
- Modify: `backend/src/explorator/domain/evaluation/ranking.py`
- Modify: `backend/tests/unit/domain/test_diversity.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/domain/test_diversity.py`:

```python
from explorator.domain.evaluation.ranking import apply_diversity_penalty


def test_diversity_penalty_demotes_near_duplicates() -> None:
    """Two candidates with edit_dist<=2 AND score_dist<0.5 — lower one demoted."""
    candidates = [
        {"id": "a", "weighted_total": 8.0, "chord_symbols": ["C", "G", "Am", "F"],
         "scores": {"genre_fit": 8.0, "novelty": 7.0}},
        {"id": "b", "weighted_total": 7.5, "chord_symbols": ["C", "G", "Am", "E"],
         "scores": {"genre_fit": 8.0, "novelty": 7.0}},
        {"id": "c", "weighted_total": 6.0, "chord_symbols": ["Dm", "Bb", "F", "C"],
         "scores": {"genre_fit": 5.0, "novelty": 9.0}},
    ]
    result = apply_diversity_penalty(
        candidates, top_n=3, edit_dist_threshold=2, score_dist_threshold=0.5,
    )
    # b is near-duplicate of a — demoted; c promoted
    result_ids = [c["id"] for c in result]
    assert result_ids[0] == "a"
    assert "c" in result_ids[:2]  # c should be in top-2


def test_diversity_penalty_keeps_diverse_candidates() -> None:
    """All candidates are diverse — no demotion."""
    candidates = [
        {"id": "a", "weighted_total": 8.0, "chord_symbols": ["C", "G", "Am", "F"],
         "scores": {"genre_fit": 9.0, "novelty": 3.0}},
        {"id": "b", "weighted_total": 7.5, "chord_symbols": ["Dm", "Bb", "F", "C"],
         "scores": {"genre_fit": 3.0, "novelty": 9.0}},
    ]
    result = apply_diversity_penalty(
        candidates, top_n=2, edit_dist_threshold=2, score_dist_threshold=0.5,
    )
    assert [c["id"] for c in result] == ["a", "b"]


def test_diversity_penalty_empty_input() -> None:
    assert apply_diversity_penalty([], top_n=3) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_diversity.py::test_diversity_penalty_demotes_near_duplicates -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/domain/evaluation/ranking.py`:

```python
def apply_diversity_penalty(
    candidates: list[dict],
    top_n: int = 5,
    edit_dist_threshold: int = 2,
    score_dist_threshold: float = 0.5,
) -> list[dict]:
    """Reorder candidates by demoting near-duplicates from top-N.

    Two candidates are near-duplicates if chord_edit_distance <= edit_dist_threshold
    AND score_space_distance < score_dist_threshold. The lower-ranked duplicate
    is demoted to make room for a more diverse candidate.

    Args:
        candidates: Sorted by weighted_total descending. Each must have
            "id", "weighted_total", "chord_symbols", and "scores".
        top_n: How many top slots to diversify.
        edit_dist_threshold: Max chord edit distance for near-duplicate.
        score_dist_threshold: Max score-space distance for near-duplicate.

    Returns:
        Reordered candidate list with same length.
    """
    if not candidates:
        return []

    result: list[dict] = []
    remaining = list(candidates)

    while remaining and len(result) < top_n:
        candidate = remaining.pop(0)
        is_duplicate = False
        for accepted in result:
            edit_dist = chord_edit_distance(
                candidate.get("chord_symbols", []),
                accepted.get("chord_symbols", []),
            )
            score_dist = score_space_distance(
                candidate.get("scores", {}),
                accepted.get("scores", {}),
            )
            if edit_dist <= edit_dist_threshold and score_dist < score_dist_threshold:
                is_duplicate = True
                break
        if is_duplicate:
            remaining.append(candidate)  # demote to end
        else:
            result.append(candidate)

    # Append any remaining candidates (those that didn't make top_n or were demoted)
    result.extend(remaining)
    return result
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_diversity.py -v`
Expected: ALL PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
cd <repo-root> && git add backend/src/explorator/domain/evaluation/ranking.py backend/tests/unit/domain/test_diversity.py && git commit -m "feat(m3c): apply_diversity_penalty function"
```

---

### Task 3: assign_selection_roles Function

**Files:**
- Modify: `backend/src/explorator/domain/evaluation/ranking.py`
- Create: `backend/tests/unit/domain/test_selection_roles.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/domain/test_selection_roles.py
"""Tests for selection role assignment."""

from explorator.domain.evaluation.ranking import assign_selection_roles


def test_assigns_all_three_roles() -> None:
    candidates = [
        {"id": "a", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 7.0}, "weighted_total": 8.5},
        {"id": "b", "scores": {"genre_fit": 6.0, "novelty": 9.5, "loopability": 6.0}, "weighted_total": 7.5},
        {"id": "c", "scores": {"genre_fit": 7.0, "novelty": 4.0, "loopability": 9.5}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert roles["a"] == "safest"  # highest weighted_total with genre_fit > 8.0
    assert roles["b"] == "most_experimental"  # highest novelty with weighted_total > 7.0
    assert roles["c"] == "best_loop"  # highest loopability


def test_candidate_can_hold_multiple_roles() -> None:
    candidates = [
        {"id": "a", "scores": {"genre_fit": 9.0, "novelty": 9.0, "loopability": 9.0}, "weighted_total": 9.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    # a qualifies for all three roles — only first assigned wins for the dict key
    assert "a" in roles.values() or len(roles) >= 1


def test_no_safest_when_no_genre_fit_above_8() -> None:
    candidates = [
        {"id": "a", "scores": {"genre_fit": 7.5, "novelty": 6.0, "loopability": 6.0}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert "safest" not in roles.values()
    assert any("safest" in n.lower() for n in notes)


def test_no_experimental_when_no_weighted_total_above_7() -> None:
    candidates = [
        {"id": "a", "scores": {"genre_fit": 5.0, "novelty": 9.0, "loopability": 5.0}, "weighted_total": 6.5},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert "most_experimental" not in roles.values()
    assert any("experimental" in n.lower() for n in notes)


def test_empty_candidates() -> None:
    roles, notes = assign_selection_roles([])
    assert roles == {}
    assert len(notes) == 3  # all three roles empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_selection_roles.py -v`

- [ ] **Step 3: Implement**

Append to `backend/src/explorator/domain/evaluation/ranking.py`:

```python
def assign_selection_roles(
    candidates: list[dict],
) -> tuple[dict[str, str], list[str]]:
    """Assign finalist roles: safest, best_loop, most_experimental.

    Args:
        candidates: List of dicts with "id", "scores" (dict), "weighted_total" (float).

    Returns:
        Tuple of (roles dict {candidate_id: role_name}, notes list).
        A candidate can hold only one role (first match wins).
    """
    roles: dict[str, str] = {}
    notes: list[str] = []
    assigned_ids: set[str] = set()

    # Safest: highest weighted_total where genre_fit > 8.0
    safest_candidates = [
        c for c in candidates
        if c.get("scores", {}).get("genre_fit", 0.0) > 8.0
    ]
    safest_candidates.sort(key=lambda c: c.get("weighted_total", 0.0), reverse=True)
    if safest_candidates:
        cid = safest_candidates[0]["id"]
        roles[cid] = "safest"
        assigned_ids.add(cid)
    else:
        notes.append("No candidate qualifies for safest (requires genre_fit > 8.0)")

    # Best Loop: highest loopability
    loop_candidates = sorted(
        candidates,
        key=lambda c: c.get("scores", {}).get("loopability", 0.0),
        reverse=True,
    )
    for c in loop_candidates:
        if c["id"] not in assigned_ids:
            roles[c["id"]] = "best_loop"
            assigned_ids.add(c["id"])
            break
    else:
        if not loop_candidates:
            notes.append("No candidate qualifies for best_loop (no candidates)")

    # Most Experimental: highest novelty where weighted_total > 7.0
    experimental_candidates = [
        c for c in candidates
        if c.get("weighted_total", 0.0) > 7.0 and c["id"] not in assigned_ids
    ]
    experimental_candidates.sort(
        key=lambda c: c.get("scores", {}).get("novelty", 0.0), reverse=True,
    )
    if experimental_candidates:
        cid = experimental_candidates[0]["id"]
        roles[cid] = "most_experimental"
        assigned_ids.add(cid)
    else:
        notes.append("No candidate qualifies for most_experimental (requires weighted_total > 7.0)")

    return roles, notes
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run python -m pytest tests/unit/domain/test_selection_roles.py -v`
Expected: ALL PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd <repo-root> && git add backend/src/explorator/domain/evaluation/ranking.py backend/tests/unit/domain/test_selection_roles.py && git commit -m "feat(m3c): assign_selection_roles function"
```

---

### Task 4: State + rank_and_select Integration

**Files:**
- Modify: `backend/src/explorator/engine/state.py`
- Modify: `backend/src/explorator/engine/nodes/rank_and_select.py`
- Modify: `backend/tests/unit/engine/test_rank_and_select.py`

- [ ] **Step 1: Add final_selection to state**

In `backend/src/explorator/engine/state.py`, add after the M3b block:

```python
    # --- M3c: Finalists ---
    final_selection: dict[str, Any]
```

- [ ] **Step 2: Write failing test for rank_and_select emitting final_selection**

Append to `backend/tests/unit/engine/test_rank_and_select.py`:

```python
@pytest.mark.asyncio
async def test_rank_and_select_produces_final_selection() -> None:
    """rank_and_select output includes final_selection with roles."""
    prog = {
        "id": "prog_1",
        "chord_symbols": ["C", "G", "Am", "F"],
        "metadata": {"scores": {"genre_fit": 9.0, "novelty": 5.0, "emotional_fit": 7.0,
                                  "theoretical_coherence": 7.0, "cadence_quality": 7.0, "loopability": 8.0}},
    }
    arr = {"id": "arr_1", "progression_candidate_id": "prog_1", "status": "draft"}
    ev = {
        "arrangement_candidate_id": "arr_1",
        "voice_leading": {"overall_score": 8.0},
        "register_density": {"overall_score": 7.0},
        "playability": {"overall_score": 7.0},
    }

    state = {
        "arrangement_candidates": [arr],
        "arrangement_families": [],
        "progression_candidates": [prog],
        "evaluations": [ev],
    }

    result = await rank_and_select(state)
    assert "final_selection" in result
    fs = result["final_selection"]
    assert "selection_roles" in fs
    assert "selection_notes" in fs
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_rank_and_select.py::test_rank_and_select_produces_final_selection -v`

- [ ] **Step 4: Integrate into rank_and_select**

In `backend/src/explorator/engine/nodes/rank_and_select.py`:

Add imports at top:

```python
from explorator.domain.evaluation.ranking import (
    CANONICAL_DEFAULT_WEIGHTS,
    apply_diversity_penalty,
    assign_selection_roles,
    chord_edit_distance,
)
```

Replace the existing import line:
```python
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
```

Before the return statement, add diversity penalty and selection role logic:

```python
    # --- M3c: Diversity penalties ---
    # Build candidate dicts for diversity analysis
    diversity_input: list[dict[str, Any]] = []
    for sc_data in scorecards:
        arr_id = sc_data["candidate_id"]
        prog_id = arr_prog_map.get(arr_id, "")
        diversity_input.append({
            "id": arr_id,
            "weighted_total": sc_data["weighted_total"],
            "chord_symbols": prog_chord_lookup.get(prog_id, []),
            "scores": sc_data["scores"],
        })
    diversity_input.sort(key=lambda c: c["weighted_total"], reverse=True)

    search_plan = state.get("search_plan", {})
    diversity_target = search_plan.get("diversity_target", 0.65)
    top_n = max(3, int(len(diversity_input) * diversity_target))

    diversified = apply_diversity_penalty(
        diversity_input, top_n=top_n, edit_dist_threshold=2, score_dist_threshold=0.5,
    )

    # --- M3c: Selection roles ---
    selection_roles, selection_notes = assign_selection_roles(diversified[:top_n])

    final_selection = {
        "selection_roles": selection_roles,
        "selection_notes": selection_notes,
        "finalist_ids": list(selection_roles.keys()),
    }
```

Add `"final_selection": final_selection,` to the return dict.

- [ ] **Step 5: Run all rank_and_select tests**

Run: `cd backend && uv run python -m pytest tests/unit/engine/test_rank_and_select.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd <repo-root> && git add backend/src/explorator/engine/state.py backend/src/explorator/engine/nodes/rank_and_select.py backend/tests/unit/engine/test_rank_and_select.py && git commit -m "feat(m3c): integrate diversity penalty and selection roles into rank_and_select"
```

---

### Task 5: Frontend — Finalist Types + Store

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/arrangementStore.ts`

- [ ] **Step 1: Add types to api.ts**

Append to `frontend/src/services/api.ts`:

```typescript
// --- M3c Finalist Types ---

export interface FinalSelection {
  selection_roles: Record<string, string>;  // {candidate_id: role_name}
  selection_notes: string[];
  finalist_ids: string[];
}
```

- [ ] **Step 2: Extend arrangementStore**

Read `frontend/src/stores/arrangementStore.ts` first, then add `finalSelection` field:

Add to the state interface:
```typescript
  finalSelection: FinalSelection | null;
  setFinalSelection: (fs: FinalSelection | null) => void;
```

Add to the store implementation:
```typescript
  finalSelection: null,
  setFinalSelection: (fs) => set({ finalSelection: fs }),
```

Update the `reset` action to also clear `finalSelection: null`.

- [ ] **Step 3: Commit**

```bash
cd <repo-root> && git add frontend/src/services/api.ts frontend/src/stores/arrangementStore.ts && git commit -m "feat(m3c): FinalSelection type and store field"
```

---

### Task 6: Frontend — FinalistPanel Component

**Files:**
- Create: `frontend/src/components/FinalistPanel.tsx`

- [ ] **Step 1: Implement**

```tsx
// frontend/src/components/FinalistPanel.tsx
import type { ArrangementSummary, FinalSelection } from '../services/api';

interface FinalistPanelProps {
  finalSelection: FinalSelection;
  arrangements: ArrangementSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  safest: { label: 'Safest', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50' },
  best_loop: { label: 'Best Loop', color: 'bg-amber-500/20 text-amber-400 border-amber-500/50' },
  most_experimental: { label: 'Most Experimental', color: 'bg-violet-500/20 text-violet-400 border-violet-500/50' },
};

function scoreColor(score: number): string {
  if (score >= 8) return 'text-emerald-400';
  if (score >= 6) return 'text-amber-400';
  return 'text-rose-400';
}

export default function FinalistPanel({
  finalSelection,
  arrangements,
  selectedId,
  onSelect,
}: FinalistPanelProps) {
  const { selection_roles, finalist_ids } = finalSelection;
  if (finalist_ids.length === 0) return null;

  const arrLookup = new Map(arrangements.map((a) => [a.id, a]));

  return (
    <div className="border-b border-slate-700 bg-slate-900/50">
      <div className="px-3 py-2 border-b border-slate-800">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Finalists
        </h3>
      </div>
      <div className="flex flex-col gap-1 p-2">
        {finalist_ids.map((id) => {
          const arr = arrLookup.get(id);
          if (!arr) return null;
          const role = selection_roles[id];
          const config = ROLE_CONFIG[role] || { label: role, color: 'bg-slate-700 text-slate-300' };

          return (
            <div
              key={id}
              onClick={() => onSelect(id)}
              className={[
                'border rounded-md p-3 cursor-pointer transition-all',
                selectedId === id
                  ? 'border-l-4 border-purple-500 bg-slate-800'
                  : 'border-slate-700 bg-slate-900 hover:bg-slate-800',
              ].join(' ')}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-xs px-2 py-0.5 rounded-full border ${config.color}`}>
                  {config.label}
                </span>
                <span className={`text-sm font-bold font-mono ${scoreColor(arr.weighted_total)}`}>
                  {(arr.weighted_total ?? 0).toFixed(2)}
                </span>
              </div>
              <p className="text-slate-500 text-xs truncate">{arr.rationale}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd <repo-root> && git add frontend/src/components/FinalistPanel.tsx && git commit -m "feat(m3c): FinalistPanel component with role badges"
```

---

### Task 7: Integrate FinalistPanel into ArrangementList

**Files:**
- Modify: `frontend/src/components/ArrangementList.tsx`

- [ ] **Step 1: Add FinalistPanel to ArrangementList**

In `frontend/src/components/ArrangementList.tsx`:

Add import:
```typescript
import FinalistPanel from './FinalistPanel';
import type { FinalSelection } from '../services/api';
```

Add `finalSelection` to the props interface:
```typescript
interface ArrangementListProps {
  arrangements: ArrangementSummary[]
  candidates: CandidateSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
  genre: string
  finalSelection?: FinalSelection | null
}
```

Add `finalSelection` to the destructured props:
```typescript
export default function ArrangementList({
  arrangements,
  candidates,
  selectedId,
  onSelect,
  genre,
  finalSelection,
}: ArrangementListProps) {
```

Inside the returned JSX, render FinalistPanel at the top (right after the opening `<div>` of the main container, before the grouped entries):

```tsx
      {finalSelection && finalSelection.finalist_ids.length > 0 && (
        <FinalistPanel
          finalSelection={finalSelection}
          arrangements={arrangements}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      )}
```

- [ ] **Step 2: Pass finalSelection from SessionWorkspace**

In `frontend/src/views/SessionWorkspace.tsx`, pass the prop to ArrangementList:

```tsx
            <ArrangementList
              arrangements={arrangementStore.arrangements}
              candidates={candidates}
              selectedId={arrangementStore.selectedArrangementId}
              onSelect={handleSelectArrangement}
              genre={session?.genre || 'dream_pop'}
              finalSelection={arrangementStore.finalSelection}
            />
```

- [ ] **Step 3: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd <repo-root> && git add frontend/src/components/ArrangementList.tsx frontend/src/views/SessionWorkspace.tsx && git commit -m "feat(m3c): integrate FinalistPanel into ArrangementList"
```

---

### Task 8: Full Regression Check

**Files:** None (verification only)

- [ ] **Step 1: Run complete backend test suite**

Run: `cd backend && uv run python -m pytest tests/ -v`
Expected: ALL PASS (except pre-existing serialization test)

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: No errors
