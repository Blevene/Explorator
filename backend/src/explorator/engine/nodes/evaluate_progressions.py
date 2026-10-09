"""Evaluate progressions node — hybrid theory scoring with parallel execution."""

import asyncio
import logging
from typing import Any

from explorator.adapters.llm import LLMClient
from explorator.domain.evaluation.theory import TheoryEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)


async def evaluate_progressions(
    state: ExplorationState, *, gemini: LLMClient
) -> dict[str, Any]:
    """Score all progression candidates on theory dimensions.

    Evaluations run in parallel via asyncio.gather() for speed.
    """
    callback = state.get("on_progress")
    if callback:
        n = len(state.get("progression_candidates", []))
        await callback("node_started", {"node": "evaluate_progressions", "count": n})

    evaluator = TheoryEvaluator(gemini)
    brief = parse_json_or_dict(state.get("creative_brief", {}))
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
    failed = 0
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            logger.error(
                "Evaluation failed for candidate %s: %s",
                candidates[i].id if i < len(candidates) else "unknown",
                result,
                exc_info=result,
            )
            failed += 1
            continue
        theory_eval, scorecard = result
        evaluations.append(theory_eval.model_dump(mode="json"))
        scorecards.append(scorecard.model_dump(mode="json"))

    if failed > 0:
        logger.warning(
            "Evaluated %d/%d candidates (%d failed)",
            len(scorecards), len(candidates), failed,
        )

    if callback:
        top_score = max((s["weighted_total"] for s in scorecards), default=0)
        await callback(
            "node_completed",
            {
                "node": "evaluate_progressions",
                "evaluated": len(scorecards),
                "failed": failed,
                "top_score": top_score,
            },
        )

    return {"evaluations": evaluations, "scorecards": scorecards}
