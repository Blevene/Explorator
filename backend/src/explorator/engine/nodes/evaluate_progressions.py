"""Evaluate progressions node — hybrid theory scoring with parallel execution."""

import asyncio
from typing import Any

from explorator.adapters.gemini import GeminiClient
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate


async def evaluate_progressions(
    state: ExplorationState, *, gemini: GeminiClient
) -> dict[str, Any]:
    """Score all progression candidates on theory dimensions.

    Evaluations run in parallel via asyncio.gather() for speed.
    """
    callback = state.get("on_progress")
    if callback:
        n = len(state.get("progression_candidates", []))
        await callback("node_started", {"node": "evaluate_progressions", "count": n})

    evaluator = TheoryEvaluator(gemini)
    brief = state.get("creative_brief", {})
    genre = state.get("genre", "dream_pop")
    mood_targets = brief.get("mood_targets", [])

    candidates = [
        ProgressionCandidate.model_validate(d)
        for d in state.get("progression_candidates", [])
    ]

    # Evaluate all candidates in parallel
    results = await asyncio.gather(
        *(evaluator.evaluate(c, genre, mood_targets) for c in candidates),
        return_exceptions=True,
    )

    evaluations = []
    scorecards = []
    for result in results:
        if isinstance(result, BaseException):
            continue  # Skip failed evaluations
        theory_eval, scorecard = result
        evaluations.append(theory_eval.model_dump(mode="json"))
        scorecards.append(scorecard.model_dump(mode="json"))

    if callback:
        top_score = max((s["weighted_total"] for s in scorecards), default=0)
        await callback(
            "node_completed",
            {"node": "evaluate_progressions", "evaluated": len(scorecards), "top_score": top_score},
        )

    return {"evaluations": evaluations, "scorecards": scorecards}
