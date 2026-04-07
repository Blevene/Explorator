"""Unit tests for rank_and_select helper functions."""

from __future__ import annotations

import pytest

from explorator.engine.nodes.rank_and_select import (
    DEFAULT_WEIGHTS,
    _compute_weighted_total,
    _rank_family,
)


# ---------------------------------------------------------------------------
# _compute_weighted_total
# ---------------------------------------------------------------------------


def test_compute_weighted_total_all_perfect() -> None:
    """All scores at 10.0 → weighted total = 10.0."""
    scores = {dim: 10.0 for dim in DEFAULT_WEIGHTS}
    result = _compute_weighted_total(scores, DEFAULT_WEIGHTS)
    assert abs(result - 10.0) < 0.01


def test_compute_weighted_total_all_zero() -> None:
    """All scores at 0.0 → weighted total = 0.0."""
    scores = {dim: 0.0 for dim in DEFAULT_WEIGHTS}
    result = _compute_weighted_total(scores, DEFAULT_WEIGHTS)
    assert result == 0.0


def test_compute_weighted_total_missing_m1_scores_uses_fallback() -> None:
    """M1 dimensions missing from scores → 5.0 fallback applied."""
    # Only supply M2b scores; M1 dimensions (genre_fit etc.) are absent
    scores = {
        "voice_leading": 8.0,
        "register_density": 8.0,
        "playability": 8.0,
    }
    result = _compute_weighted_total(scores, DEFAULT_WEIGHTS)

    # Compute expected manually using 5.0 fallback for M1 dims
    expected = (
        8.0 * DEFAULT_WEIGHTS["voice_leading"]
        + 8.0 * DEFAULT_WEIGHTS["register_density"]
        + 8.0 * DEFAULT_WEIGHTS["playability"]
        + 5.0 * DEFAULT_WEIGHTS["genre_fit"]
        + 5.0 * DEFAULT_WEIGHTS["emotional_fit"]
        + 5.0 * DEFAULT_WEIGHTS["theoretical_coherence"]
        + 5.0 * DEFAULT_WEIGHTS["cadence_quality"]
        + 5.0 * DEFAULT_WEIGHTS["novelty"]
        + 5.0 * DEFAULT_WEIGHTS["loopability"]
    )
    assert abs(result - expected) < 0.001


# ---------------------------------------------------------------------------
# _rank_family
# ---------------------------------------------------------------------------


def _make_candidate(cid: str, scores: dict[str, float]) -> dict:
    return {"id": cid, "merged_scores": scores}


def _perfect_scores() -> dict[str, float]:
    return {dim: 10.0 for dim in DEFAULT_WEIGHTS}


def test_rank_family_rejects_below_threshold() -> None:
    """Candidates with any gate dimension < 3.0 are excluded."""
    good = _make_candidate("good", _perfect_scores())
    bad = _make_candidate("bad", {**_perfect_scores(), "voice_leading": 2.0})

    result = _rank_family([good, bad], DEFAULT_WEIGHTS)
    ids = [c["id"] for c in result]
    assert "good" in ids
    assert "bad" not in ids


def test_rank_family_selects_top_2() -> None:
    """Top 2 highest-scoring candidates are returned."""
    scores_a = {**_perfect_scores(), "voice_leading": 10.0}  # best
    scores_b = {**_perfect_scores(), "voice_leading": 8.0}   # second
    scores_c = {**_perfect_scores(), "voice_leading": 6.0}   # third

    cands = [
        _make_candidate("c", scores_c),
        _make_candidate("a", scores_a),
        _make_candidate("b", scores_b),
    ]
    result = _rank_family(cands, DEFAULT_WEIGHTS, top_n=2)
    assert len(result) == 2
    assert result[0]["id"] == "a"
    assert result[1]["id"] == "b"


def test_rank_family_keeps_all_if_fewer_than_top_n_survive() -> None:
    """If only 1 candidate survives filtering, return that 1 (< top_n=2)."""
    good = _make_candidate("only", _perfect_scores())
    bad = _make_candidate("bad", {**_perfect_scores(), "register_density": 1.0})

    result = _rank_family([good, bad], DEFAULT_WEIGHTS, top_n=2)
    assert len(result) == 1
    assert result[0]["id"] == "only"


def test_rank_family_all_rejected_returns_empty() -> None:
    """All candidates below threshold → empty list returned."""
    bad1 = _make_candidate("x", {**_perfect_scores(), "playability": 0.0})
    bad2 = _make_candidate("y", {**_perfect_scores(), "voice_leading": 2.9})

    result = _rank_family([bad1, bad2], DEFAULT_WEIGHTS)
    assert result == []


def test_rank_family_empty_input() -> None:
    """Empty candidate list returns empty list."""
    assert _rank_family([], DEFAULT_WEIGHTS) == []
