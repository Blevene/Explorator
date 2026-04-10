"""check_stop node — evaluate stop conditions after each round."""

import logging
from typing import Any

from explorator.engine.state import ExplorationState

logger = logging.getLogger(__name__)


async def check_stop(state: ExplorationState) -> dict[str, Any]:
    """Check stop conditions. Deterministic — no Gemini call.

    Conditions (stop on ANY):
    1. Quality: top candidate weighted_total >= target_score
    2. Diversity: >= 3 pairwise-diverse candidates on Pareto front
    3. Budget: round_number >= max_rounds
    4. User satisfaction: feedback_history contains positive satisfaction
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "check_stop"})

    plan = state.get("search_plan", {})
    stop_conditions = plan.get("stop_conditions", {})
    target_score = stop_conditions.get("target_score", 8.5)
    max_rounds = stop_conditions.get("max_rounds", 4)

    round_number = state.get("round_number", 1)
    scorecards = state.get("scorecards", [])
    pareto = state.get("pareto_front", {})

    # Condition 1: Quality threshold
    if scorecards:
        top_score = max(sc.get("weighted_total", 0.0) for sc in scorecards)
        if top_score >= target_score:
            logger.info("Stop: quality threshold met (%.2f >= %.2f)", top_score, target_score)
            return {"stop_condition_met": True, "stop_reason": "quality"}

    # Condition 2: Diversity sufficient
    pareto_ids = pareto.get("candidate_ids", [])
    pairwise_diverse = pareto.get("pairwise_diverse", False)
    if len(pareto_ids) >= 3 and pairwise_diverse:
        logger.info("Stop: diversity sufficient (%d Pareto candidates)", len(pareto_ids))
        return {"stop_condition_met": True, "stop_reason": "diversity"}

    # Condition 3: Budget exhausted
    if round_number >= max_rounds:
        logger.info("Stop: budget exhausted (round %d >= %d)", round_number, max_rounds)
        return {"stop_condition_met": True, "stop_reason": "budget"}

    # Condition 4: User satisfaction (M3b) — only the most recent feedback counts
    feedback_history = state.get("feedback_history", [])
    if feedback_history:
        latest_fb = feedback_history[-1]
        adjustments = latest_fb.get("interpreted_adjustments", {})
        if adjustments.get("satisfaction") == "positive":
            logger.info("Stop: user expressed satisfaction in feedback %s", latest_fb.get("id", "?"))
            return {"stop_condition_met": True, "stop_reason": "satisfaction"}

    logger.info("Continue: no stop condition met (round %d, top=%.2f)",
                round_number, max(
                    (sc.get("weighted_total", 0.0) for sc in scorecards),
                    default=0.0,
                ))
    return {"stop_condition_met": False, "stop_reason": ""}
