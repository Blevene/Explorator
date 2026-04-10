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
        {"id": "c", "scores": {"x": 4.0, "y": 4.0, "z": 4.0}},
    ]
    front = compute_pareto_front(candidates, axes=["x", "y", "z"])
    # c is non-dominated: a beats on x but loses on y; b beats on y but loses on x
    assert "c" in front


def test_empty_candidates() -> None:
    assert compute_pareto_front([], axes=["x"]) == []


def test_missing_score_defaults_to_zero() -> None:
    candidates = [
        {"id": "a", "scores": {"x": 5.0}},
        {"id": "b", "scores": {"x": 3.0, "y": 8.0}},
    ]
    front = compute_pareto_front(candidates, axes=["x", "y"])
    assert set(front) == {"a", "b"}
