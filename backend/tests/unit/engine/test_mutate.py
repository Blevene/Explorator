"""Tests for the mutate node."""

from unittest.mock import AsyncMock, MagicMock

from explorator.domain.harmony.mutator import MutationResponse, MutationResponseItem
from explorator.engine.nodes.mutate import mutate, _select_candidates_to_mutate


def test_select_candidates_prioritizes_pareto() -> None:
    scorecards = [
        {"candidate_id": "a", "weighted_total": 9.0},
        {"candidate_id": "b", "weighted_total": 8.0},
        {"candidate_id": "c", "weighted_total": 7.0},
        {"candidate_id": "d", "weighted_total": 6.0},
    ]
    pareto_ids = ["c", "d"]
    result = _select_candidates_to_mutate(
        scorecards=scorecards,
        pareto_ids=pareto_ids,
        budget=3,
    )
    assert "c" in result
    assert "d" in result
    assert len(result) == 3


def test_select_candidates_respects_budget() -> None:
    scorecards = [
        {"candidate_id": "a", "weighted_total": 9.0},
        {"candidate_id": "b", "weighted_total": 8.0},
    ]
    result = _select_candidates_to_mutate(scorecards=scorecards, pareto_ids=[], budget=1)
    assert len(result) == 1
    assert result[0] == "a"


async def test_mutate_returns_merged_candidates() -> None:
    """mutate must return existing + new candidates (not just new)."""
    mock_mutator_response = MutationResponse(
        mutated_chord_symbols=["Dm7", "G7", "Cmaj7"],
        mutations=[
            MutationResponseItem(
                operation="substitute_chord",
                position=0,
                original_value="Am7",
                new_value="Dm7",
                reason="test",
            ),
        ],
    )

    mock_gemini = MagicMock()
    mock_gemini.generate_structured = AsyncMock(return_value=mock_mutator_response)

    existing_prog = {
        "id": "pc_01",
        "chord_symbols": ["Am7", "G7", "Cmaj7"],
        "metadata": {"scores": {"genre_fit": 7.0, "novelty": 5.0}},
    }

    state = {
        "session_id": "sess_01",
        "genre": "dream_pop",
        "genre_profile": {"genre": "dream_pop"},
        "search_plan": {"mutation_budget_per_round": 2},
        "round_number": 1,
        "progression_candidates": [existing_prog],
        "top_progressions": [existing_prog],
        "scorecards": [{"candidate_id": "arr_01", "weighted_total": 7.0, "scores": {"genre_fit": 7.0, "novelty": 5.0}}],
        "pareto_front": {"candidate_ids": ["arr_01"]},
        "mutation_records": [],
        "all_candidates_history": [],
        "arrangement_candidates": [{"id": "arr_01", "progression_candidate_id": "pc_01"}],
    }

    result = await mutate(state, gemini=mock_gemini)

    # Must include existing + new
    prog_ids = [p["id"] for p in result["progression_candidates"]]
    assert "pc_01" in prog_ids
    assert len(prog_ids) > 1

    # Mutation records populated
    assert len(result["mutation_records"]) > 0

    # Stale downstream fields cleared (harmonic mutation)
    assert result["voicing_plans"] == []
    assert result["arrangement_candidates"] == []
    assert result["evaluations"] == []

    # Round incremented
    assert result["round_number"] == 2
