# backend/tests/unit/engine/test_load_memory.py
"""Tests for load_memory node."""

import pytest
from unittest.mock import AsyncMock, patch

from explorator.engine.nodes.load_memory import load_memory
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS


def _make_state(session_id: str = "sess_1") -> dict:
    return {"session_id": session_id}


@pytest.mark.asyncio
async def test_load_memory_returns_defaults_when_no_feedback() -> None:
    mock_driver = AsyncMock()

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(return_value=[])
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(return_value=None)

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert result["feedback_history"] == []
    assert result["objective_weights"] == CANONICAL_DEFAULT_WEIGHTS.weights
    assert result["user_preference_profile"] == {}


@pytest.mark.asyncio
async def test_load_memory_returns_existing_feedback() -> None:
    mock_driver = AsyncMock()
    feedback = [{"id": "fb_1", "content": "too dark"}]
    custom_weights = {"genre_fit": 0.20, "novelty": 0.15}

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(return_value=feedback)
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(
            return_value={"weights": custom_weights}
        )

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert len(result["feedback_history"]) == 1
    assert result["objective_weights"] == custom_weights


@pytest.mark.asyncio
async def test_load_memory_timeout_returns_defaults() -> None:
    """If Neo4j times out, return safe defaults."""
    mock_driver = AsyncMock()

    with patch(
        "explorator.engine.nodes.load_memory.FeedbackEventRepo"
    ) as MockFBRepo, patch(
        "explorator.engine.nodes.load_memory.ObjectiveWeightsRepo"
    ) as MockOWRepo:
        MockFBRepo.return_value.list_by_session = AsyncMock(
            side_effect=TimeoutError("Neo4j timeout")
        )
        MockOWRepo.return_value.get_latest_for_session = AsyncMock(
            side_effect=TimeoutError("Neo4j timeout")
        )

        state = _make_state()
        result = await load_memory(state, driver=mock_driver)

    assert result["feedback_history"] == []
    assert result["objective_weights"] == CANONICAL_DEFAULT_WEIGHTS.weights
    assert result["user_preference_profile"] == {}
