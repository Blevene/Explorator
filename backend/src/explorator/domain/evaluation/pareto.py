"""Pareto front identification for multi-objective candidate ranking."""

from typing import Any


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
    candidates: list[dict[str, Any]],
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
