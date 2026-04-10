"""Tests for selection role assignment."""

from explorator.domain.evaluation.ranking import assign_selection_roles


def test_assigns_all_three_roles() -> None:
    candidates = [
        {"id": "a", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 7.0}, "weighted_total": 8.5},
        {"id": "b", "scores": {"genre_fit": 6.0, "novelty": 9.5, "loopability": 6.0}, "weighted_total": 7.5},
        {"id": "c", "scores": {"genre_fit": 7.0, "novelty": 4.0, "loopability": 9.5}, "weighted_total": 7.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    assert roles["a"] == "safest"
    assert roles["b"] == "most_experimental"
    assert roles["c"] == "best_loop"


def test_single_candidate_gets_one_role() -> None:
    """One candidate qualifies for all three — gets first matching role only."""
    candidates = [
        {"id": "a", "scores": {"genre_fit": 9.0, "novelty": 9.0, "loopability": 9.0}, "weighted_total": 9.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    # Only one role assigned per candidate (first match wins)
    assert len(roles) == 1
    assert "a" in roles


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
    assert len(notes) == 3


def test_best_loop_skipped_when_all_assigned() -> None:
    """If the best loop candidate is already safest, next-best gets best_loop.
    If no next-best exists, note is added."""
    candidates = [
        {"id": "a", "scores": {"genre_fit": 9.0, "novelty": 5.0, "loopability": 9.0}, "weighted_total": 9.0},
    ]
    roles, notes = assign_selection_roles(candidates)
    # a gets safest (first role), best_loop can't be assigned (only candidate taken)
    assert roles.get("a") == "safest"
    assert any("best_loop" in n.lower() for n in notes)
