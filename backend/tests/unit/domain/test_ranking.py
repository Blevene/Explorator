"""Tests for candidate ranking."""

from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS, select_top_k, weighted_score
from explorator.models.evaluation import AggregateScorecard, ObjectiveWeights


def test_weighted_score_calculation() -> None:
    weights = ObjectiveWeights(
        id="w1", type="weights", status="active",
        weights={"genre_fit": 0.5, "novelty": 0.5},
    )
    scorecard = AggregateScorecard(
        id="s1", type="scorecard", status="active", candidate_id="c1",
        scores={"genre_fit": 8.0, "novelty": 6.0},
    )
    result = weighted_score(scorecard, weights)
    assert abs(result - 7.0) < 0.01  # (8.0*0.5 + 6.0*0.5)


def test_select_top_k_returns_k_items() -> None:
    scorecards = [
        AggregateScorecard(
            id=f"s{i}", type="scorecard", status="active",
            candidate_id=f"c{i}", scores={"genre_fit": float(i)},
            weighted_total=float(i),
        )
        for i in range(10)
    ]
    top = select_top_k(scorecards, k=3)
    assert len(top) == 3
    # Highest scores first
    assert top[0].weighted_total == 9.0
    assert top[1].weighted_total == 8.0
    assert top[2].weighted_total == 7.0


def test_select_top_k_with_fewer_than_k() -> None:
    scorecards = [
        AggregateScorecard(
            id="s1", type="scorecard", status="active",
            candidate_id="c1", scores={}, weighted_total=5.0,
        )
    ]
    top = select_top_k(scorecards, k=5)
    assert len(top) == 1


def test_canonical_weights_sum_to_one() -> None:
    """Canonical 9-dimensional weights sum to 1.0."""
    total = sum(CANONICAL_DEFAULT_WEIGHTS.weights.values())
    assert abs(total - 1.0) < 0.01


def test_canonical_weights_have_all_nine_dimensions() -> None:
    """Canonical weights cover all 6 theory + 3 arrangement dimensions."""
    expected = {
        "genre_fit", "emotional_fit", "theoretical_coherence",
        "cadence_quality", "novelty", "loopability",
        "voice_leading", "register_density", "playability",
    }
    assert set(CANONICAL_DEFAULT_WEIGHTS.weights.keys()) == expected
