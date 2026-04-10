"""Tests for FeedbackInterpreter domain service."""

from unittest.mock import AsyncMock

import pytest

from explorator.domain.intent.feedback import (
    FeedbackInterpretation,
    FeedbackInterpreter,
    apply_weight_deltas,
)
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS


def test_feedback_interpretation_model() -> None:
    fi = FeedbackInterpretation(
        interpreted_adjustments={"reduce_bass_motion": True},
        weight_deltas={"playability": 0.04, "voice_leading": -0.02, "novelty": -0.02},
        satisfaction="neutral",
    )
    assert fi.satisfaction == "neutral"
    assert fi.weight_deltas["playability"] == 0.04


def test_apply_weight_deltas_basic() -> None:
    current = {"genre_fit": 0.40, "novelty": 0.30, "loopability": 0.30}
    deltas = {"genre_fit": 0.05, "novelty": -0.05}
    result = apply_weight_deltas(current, deltas)
    # genre_fit went up, novelty went down (relative ordering preserved)
    assert result["genre_fit"] > result["novelty"]
    assert abs(sum(result.values()) - 1.0) < 0.01


def test_apply_weight_deltas_clamps_to_bounds() -> None:
    # Use a multi-dimensional case so clamping + renorm stays within bounds
    current = {"a": 0.03, "b": 0.17, "c": 0.20, "d": 0.20, "e": 0.40}
    deltas = {"a": -0.10, "e": 0.50}  # push 'a' below min, push 'e' way above max
    result = apply_weight_deltas(current, deltas)
    # 'a' should clamp to 0.02 minimum after renorm
    assert result["a"] >= 0.02
    # 'e' should be clamped so it doesn't dominate above max (0.50)
    assert result["e"] <= 0.50
    assert abs(sum(result.values()) - 1.0) < 0.01


def test_apply_weight_deltas_renormalizes() -> None:
    current = {"a": 0.30, "b": 0.30, "c": 0.40}
    deltas = {"a": 0.10, "b": 0.10}  # non-zero-sum deltas
    result = apply_weight_deltas(current, deltas)
    assert abs(sum(result.values()) - 1.0) < 0.01


@pytest.mark.asyncio
async def test_interpret_returns_feedback_interpretation() -> None:
    mock_gemini = AsyncMock()
    mock_gemini.generate_structured.return_value = FeedbackInterpretation(
        interpreted_adjustments={"prefer_open_voicings": True},
        weight_deltas={"playability": 0.03, "voice_leading": -0.03},
        satisfaction="neutral",
    )
    interpreter = FeedbackInterpreter(mock_gemini)
    result = await interpreter.interpret(
        feedback_text="prefer open voicings",
        current_weights=CANONICAL_DEFAULT_WEIGHTS.weights,
        candidate_scores={"genre_fit": 7.0},
        genre="dream_pop",
    )
    assert result.interpreted_adjustments["prefer_open_voicings"] is True
    assert result.weight_deltas["playability"] == 0.03
    mock_gemini.generate_structured.assert_called_once()
