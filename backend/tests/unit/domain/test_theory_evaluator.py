"""Tests for theory evaluator."""

from explorator.domain.evaluation.theory import (
    check_cadence_quality,
    check_loopability,
    check_theoretical_coherence,
)


def test_loopability_same_start_end() -> None:
    """Progression that starts and ends on same chord is highly loopable."""
    score = check_loopability(["Cmaj7", "Am7", "Fmaj7", "Cmaj7"])
    assert score >= 8.0


def test_loopability_different_start_end() -> None:
    """Progression with different start/end is less loopable."""
    score = check_loopability(["Cmaj7", "Am7", "Fmaj7", "G7"])
    assert score < 8.0


def test_cadence_quality_strong_resolution() -> None:
    """V-I cadence should score well."""
    score = check_cadence_quality(["Am7", "Dm7", "G7", "Cmaj7"], key="C", mode="major")
    assert score >= 7.0


def test_theoretical_coherence_diatonic() -> None:
    """Fully diatonic progression should score high coherence."""
    score = check_theoretical_coherence(
        ["Cmaj7", "Dm7", "Em7", "Fmaj7"],
        key="C",
        mode="major",
    )
    assert score >= 7.0
