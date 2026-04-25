"""Candidate ranking — weighted scoring + top-K selection."""

import math

from explorator.models.evaluation import AggregateScorecard, ObjectiveWeights

# Default M1 weights (equal weighting across theory dimensions)
DEFAULT_THEORY_WEIGHTS = ObjectiveWeights(
    id="weights_default",
    type="objective_weights",
    status="active",
    profile_name="default_theory",
    weights={
        "genre_fit": 0.20,
        "emotional_fit": 0.15,
        "theoretical_coherence": 0.20,
        "cadence_quality": 0.15,
        "novelty": 0.10,
        "loopability": 0.20,
    },
)

CANONICAL_DEFAULT_WEIGHTS = ObjectiveWeights(
    id="weights_canonical",
    type="objective_weights",
    status="active",
    profile_name="canonical_default",
    weights={
        "genre_fit": 0.10,
        "emotional_fit": 0.07,
        "theoretical_coherence": 0.08,
        "cadence_quality": 0.07,
        "novelty": 0.07,
        "loopability": 0.09,
        "voice_leading": 0.07,
        "register_density": 0.06,
        "playability": 0.06,
        "groove": 0.08,
        "melody_support": 0.15,
        "collision_risk": 0.10,
    },
)


_MELODY_DIMS = {"melody_support", "collision_risk"}


def weighted_score(
    scorecard: AggregateScorecard,
    weights: ObjectiveWeights,
    has_melody: bool = True,
) -> float:
    """Compute weighted total from scorecard and weights.

    When has_melody is False, melody dimensions are excluded and remaining
    weights are renormalized to sum to 1.0.
    """
    active_weights = weights.weights
    if not has_melody:
        active_weights = {k: v for k, v in active_weights.items() if k not in _MELODY_DIMS}
        weight_sum = sum(active_weights.values())
        if weight_sum > 0:
            active_weights = {k: v / weight_sum for k, v in active_weights.items()}
    total = 0.0
    for dim, weight in active_weights.items():
        total += scorecard.scores.get(dim, 0.0) * weight
    return round(total, 3)


def select_top_k(
    scorecards: list[AggregateScorecard],
    k: int,
) -> list[AggregateScorecard]:
    """Select top K scorecards by weighted_total, highest first."""
    sorted_cards = sorted(scorecards, key=lambda s: s.weighted_total, reverse=True)
    return sorted_cards[:k]


def chord_edit_distance(chords_a: list[str], chords_b: list[str]) -> int:
    """Count differing chord symbols between two progressions (position-wise).

    Pads the shorter progression — each missing position counts as a difference.
    """
    max_len = max(len(chords_a), len(chords_b), 0)
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
    """
    if not candidates:
        return []

    result: list[dict] = []
    remaining = list(candidates)
    demoted: set[str] = set()  # Guard against infinite loop

    while remaining and len(result) < top_n:
        candidate = remaining.pop(0)
        cid = candidate.get("id", "")

        # If already demoted once, accept it to avoid infinite loop
        if cid in demoted:
            result.append(candidate)
            continue

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
            demoted.add(cid)
            remaining.append(candidate)
        else:
            result.append(candidate)

    result.extend(remaining)
    return result


def _assign_roles_for_group(
    candidates: list[dict],
) -> tuple[dict[str, str], list[str]]:
    """Assign finalist roles within a single group of arrangement candidates.

    Each candidate gets at most one role (first match wins).
    Returns (roles dict {candidate_id: role_name}, notes list).
    """
    if not candidates:
        return {}, []

    roles: dict[str, str] = {}
    notes: list[str] = []
    assigned_ids: set[str] = set()

    # Safest: highest weighted_total where genre_fit > 7.0
    safest_candidates = [
        c for c in candidates
        if c.get("scores", {}).get("genre_fit", 0.0) > 7.0
    ]
    safest_candidates.sort(key=lambda c: c.get("weighted_total", 0.0), reverse=True)
    if safest_candidates:
        cid = safest_candidates[0]["id"]
        roles[cid] = "safest"
        assigned_ids.add(cid)

    # Best Loop: highest loopability among unassigned
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

    # Most Experimental: highest novelty among unassigned
    experimental_candidates = sorted(
        [c for c in candidates if c["id"] not in assigned_ids],
        key=lambda c: c.get("scores", {}).get("novelty", 0.0),
        reverse=True,
    )
    if experimental_candidates:
        cid = experimental_candidates[0]["id"]
        roles[cid] = "most_experimental"
        assigned_ids.add(cid)

    return roles, notes


def assign_selection_roles(
    candidates: list[dict],
) -> tuple[dict[str, str], list[str]]:
    """Assign finalist roles per progression candidate group.

    Groups arrangements by progression_candidate_id and assigns roles
    independently within each group, so every realized candidate gets
    its own safest/best_loop/most_experimental arrangements.

    Returns (roles dict {arrangement_id: role_name}, notes list).
    """
    # Group by progression_candidate_id
    groups: dict[str, list[dict]] = {}
    for c in candidates:
        prog_id = c.get("progression_candidate_id", "ungrouped")
        groups.setdefault(prog_id, []).append(c)

    all_roles: dict[str, str] = {}
    all_notes: list[str] = []

    for _prog_id, group in groups.items():
        roles, notes = _assign_roles_for_group(group)
        all_roles.update(roles)
        all_notes.extend(notes)

    return all_roles, all_notes
