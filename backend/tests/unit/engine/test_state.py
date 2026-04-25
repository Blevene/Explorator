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


def test_exploration_state_includes_realization_fields() -> None:
    """Unified state supports all M2 realization fields."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "prompt": "Dream pop",
        "progression_candidate_ids": ["pc_01", "pc_02"],
        "voicing_strategies": [{"type": "open"}],
        "voicing_plans": [{"id": "vp_01"}],
        "bass_lines": [{"id": "bl_01"}],
        "arrangement_candidates": [{"id": "arr_01"}],
        "arrangement_families": [{"id": "fam_01"}],
        "selected_arrangements": [{"id": "arr_01"}],
    }
    assert state["progression_candidate_ids"] == ["pc_01", "pc_02"]
    assert len(state["voicing_plans"]) == 1
    assert len(state["arrangement_candidates"]) == 1


def test_exploration_state_includes_m3a_fields() -> None:
    """Unified state supports M3a search and mutation fields."""
    state: ExplorationState = {
        "session_id": "sess_01",
        "search_plan": {"max_rounds": 4},
        "mutation_records": [{"id": "mr_01"}],
        "stop_condition_met": False,
        "stop_reason": "",
        "pareto_front": {"candidate_ids": []},
        "all_candidates_history": [],
    }
    assert state["stop_condition_met"] is False
    assert state["search_plan"]["max_rounds"] == 4


def test_feedback_fields_in_state() -> None:
    """M3b state fields are valid keys."""

    state: ExplorationState = {
        "feedback_history": [{"id": "fb_1", "content": "too busy"}],
        "objective_weights": {"genre_fit": 0.15, "novelty": 0.10},
        "user_preference_profile": {},
    }
    assert state["feedback_history"][0]["content"] == "too busy"
    assert state["objective_weights"]["genre_fit"] == 0.15
    assert state["user_preference_profile"] == {}
