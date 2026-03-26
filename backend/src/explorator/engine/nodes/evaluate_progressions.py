"""Evaluate progressions node — hybrid theory scoring."""

from typing import Any

from explorator.adapters.gemini import GeminiClient
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate


async def evaluate_progressions(
    state: ExplorationState, *, gemini: GeminiClient
) -> dict[str, Any]:
    """Score all progression candidates on theory dimensions."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "evaluate_progressions"})

    evaluator = TheoryEvaluator(gemini)
    brief = state.get("creative_brief", {})
    genre = state.get("genre", "dream_pop")
    mood_targets = brief.get("mood_targets", [])

    evaluations = []
    scorecards = []

    for candidate_data in state.get("progression_candidates", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)

        theory_eval, scorecard = await evaluator.evaluate(
            candidate, genre, mood_targets
        )

        evaluations.append(theory_eval.model_dump(mode="json"))
        scorecards.append(scorecard.model_dump(mode="json"))

    if callback:
        top_score = max((s["weighted_total"] for s in scorecards), default=0)
        await callback(
            "node_completed",
            {"node": "evaluate_progressions", "top_score": top_score},
        )

    return {"evaluations": evaluations, "scorecards": scorecards}
