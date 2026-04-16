"""Tests for selection role assignment (per-candidate grouping)."""

from explorator.domain.evaluation.ranking import assign_selection_roles


def test_assigns_all_three_roles() -> None:
    """Three candidates in one group — each gets a different role."""
    candidates = [
        {"id": "a", "progression_candidate_id": "p1", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 7.0}, "weighted_total": 8.5},
        {"id": "b", "progression_candidate_id": "p1", "scores": {"genre_fit": 6.0, "novelty": 9.5, "loopability": 6.0}, "weighted_total": 7.5},
        {"id": "c", "progression_candidate_id": "p1", "scores": {"genre_fit": 7.0, "novelty": 4.0, "loopability": 9.5}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert roles["a"] == "safest"
    assert roles["b"] == "most_experimental"
    assert roles["c"] == "best_loop"


def test_single_candidate_gets_one_role() -> None:
    """One candidate qualifies for all three — gets first matching role only."""
    candidates = [
        {"id": "a", "progression_candidate_id": "p1", "scores": {"genre_fit": 9.0, "novelty": 9.0, "loopability": 9.0}, "weighted_total": 9.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert len(roles) == 1
    assert "a" in roles


def test_no_safest_when_genre_fit_below_7() -> None:
    """Safest requires genre_fit > 7.0."""
    candidates = [
        {"id": "a", "progression_candidate_id": "p1", "scores": {"genre_fit": 6.5, "novelty": 6.0, "loopability": 6.0}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert "safest" not in roles.values()


def test_empty_candidates() -> None:
    roles, notes = assign_selection_roles([])
    assert roles == {}
    assert notes == []


def test_per_candidate_grouping() -> None:
    """Two progression candidates — each group gets independent roles."""
    candidates = [
        {"id": "a1", "progression_candidate_id": "p1", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 8.0}, "weighted_total": 8.0},
        {"id": "a2", "progression_candidate_id": "p1", "scores": {"genre_fit": 6.0, "novelty": 8.0, "loopability": 6.0}, "weighted_total": 7.0},
        {"id": "b1", "progression_candidate_id": "p2", "scores": {"genre_fit": 8.0, "novelty": 4.0, "loopability": 9.0}, "weighted_total": 8.5},
        {"id": "b2", "progression_candidate_id": "p2", "scores": {"genre_fit": 5.0, "novelty": 9.0, "loopability": 5.0}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)

    # p1 group: a1=safest, a2=best_loop or experimental
    assert roles["a1"] == "safest"
    assert "a2" in roles  # gets best_loop or most_experimental

    # p2 group: b1=safest, b2=something
    assert roles["b1"] == "safest"
    assert "b2" in roles

    # Total: at least 4 roles assigned (2 per group minimum)
    assert len(roles) >= 4


def test_best_loop_assigned_when_safest_taken() -> None:
    """If safest takes the highest loopability candidate, next-best gets best_loop."""
    candidates = [
        {"id": "a", "progression_candidate_id": "p1", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 9.0}, "weighted_total": 9.0},
        {"id": "b", "progression_candidate_id": "p1", "scores": {"genre_fit": 6.0, "novelty": 8.0, "loopability": 7.0}, "weighted_total": 7.5},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert roles["a"] == "safest"
    assert roles["b"] == "best_loop"
