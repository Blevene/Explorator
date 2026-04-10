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


def weighted_score(
    scorecard: AggregateScorecard,
    weights: ObjectiveWeights,
) -> float:
    """Compute weighted total from scorecard and weights."""
    total = 0.0
    for dim, weight in weights.weights.items():
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
