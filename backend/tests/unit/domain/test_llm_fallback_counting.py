"""LLM calls that fail and are silently replaced by defaults must be counted."""

from unittest.mock import AsyncMock, MagicMock

from explorator.adapters import usage
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.domain.intent.parser import IntentParser
from explorator.engine.nodes.mutate import mutate


def _failing_client() -> MagicMock:
    client = MagicMock()
    client.generate_structured = AsyncMock(side_effect=TimeoutError("request timed out"))
    return client


async def test_theory_evaluation_fallback_is_counted() -> None:
    evaluator = TheoryEvaluator(_failing_client())
    with usage.track_usage() as u:
        _, failed = await evaluator._llm_evaluate(
            ["Cmaj7", "Am7"], "dream_pop", ["wistful"], "C", "major"
        )
    assert failed is True
    assert u.fallbacks == {"evaluate_progressions": 1}


async def test_soft_preference_fallback_is_counted() -> None:
    parser = IntentParser(_failing_client())
    with usage.track_usage() as u:
        await parser._extract_soft_preferences("hazy late-night drive")
    assert u.fallbacks == {"parse_intent": 1}


async def test_mutation_failure_is_counted() -> None:
    prog = {"id": "pc_01", "chord_symbols": ["Am7", "G7", "Cmaj7"], "metadata": {}}
    state = {
        "session_id": "sess_01",
        "genre": "dream_pop",
        "genre_profile": {"genre": "dream_pop"},
        "search_plan": {"mutation_budget_per_round": 1},
        "round_number": 1,
        "progression_candidates": [prog],
        "top_progressions": [prog],
        "scorecards": [{"candidate_id": "arr_01", "weighted_total": 7.0, "scores": {}}],
        "pareto_front": {"candidate_ids": ["arr_01"]},
        "mutation_records": [],
        "all_candidates_history": [],
        "arrangement_candidates": [{"id": "arr_01", "progression_candidate_id": "pc_01"}],
    }
    with usage.track_usage() as u:
        await mutate(state, llm=_failing_client())  # type: ignore[arg-type]
    assert u.fallbacks == {"mutate": 1}
