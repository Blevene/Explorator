"""Tests for diversity distance functions."""


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
    assert abs(score_space_distance(a, b) - 5.0) < 0.01


def test_score_space_distance_missing_dims() -> None:
    a = {"x": 5.0}
    b = {"x": 5.0, "y": 3.0}
    assert abs(score_space_distance(a, b) - 3.0) < 0.01


from explorator.domain.evaluation.ranking import apply_diversity_penalty


def test_diversity_penalty_demotes_near_duplicates() -> None:
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
    result_ids = [c["id"] for c in result]
    assert result_ids[0] == "a"
    assert "c" in result_ids[:2]


def test_diversity_penalty_keeps_diverse_candidates() -> None:
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


def test_diversity_penalty_all_duplicates_doesnt_loop_forever() -> None:
    candidates = [
        {"id": f"c{i}", "weighted_total": 8.0 - i * 0.1,
         "chord_symbols": ["C", "G", "Am", "F"],
         "scores": {"genre_fit": 8.0, "novelty": 7.0}}
        for i in range(5)
    ]
    result = apply_diversity_penalty(
        candidates, top_n=3, edit_dist_threshold=2, score_dist_threshold=0.5,
    )
    assert len(result) == 5
    assert result[0]["id"] == "c0"


def test_diversity_penalty_boundary_one_condition_fails() -> None:
    """Same chords but different scores — NOT near-duplicates."""
    candidates = [
        {"id": "a", "weighted_total": 8.0, "chord_symbols": ["C", "G", "Am", "F"],
         "scores": {"genre_fit": 9.0, "novelty": 3.0}},
        {"id": "b", "weighted_total": 7.5, "chord_symbols": ["C", "G", "Am", "F"],
         "scores": {"genre_fit": 3.0, "novelty": 9.0}},
    ]
    result = apply_diversity_penalty(
        candidates, top_n=2, edit_dist_threshold=2, score_dist_threshold=0.5,
    )
    assert [c["id"] for c in result] == ["a", "b"]
