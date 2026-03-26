"""Tests for LangGraph state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from explorator.engine.state import ExplorationState


def test_exploration_state_creation() -> None:
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "Dream pop in A major",
        "genre": "dream_pop",
        "generation_mode": "balanced",
        "round_number": 1,
        "n_candidates": 12,
        "k_selection": 4,
    }
    assert state["session_id"] == "sess_01"
    assert state["round_number"] == 1


def test_exploration_state_partial() -> None:
    """State can be partially populated."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "test",
    }
    assert "genre_profile" not in state
