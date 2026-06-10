# backend/src/explorator/engine/nodes/load_memory.py
"""load_memory node — deterministic data fetch for feedback history and objective weights."""

import asyncio
import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
from explorator.engine.state import ExplorationState
from explorator.persistence.factory import (
    make_feedback_event_repo,
    make_objective_weights_repo,
)
from explorator.utils import utc_now

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


async def load_memory(
    state: ExplorationState,
    *,
    driver: AsyncDriver | None,
) -> dict[str, Any]:
    """Load feedback history and objective weights from Neo4j.

    Deterministic — no Gemini call. Falls back to canonical defaults on timeout.
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_memory"})

    session_id = state.get("session_id", "")
    fb_repo = make_feedback_event_repo(driver)
    ow_repo = make_objective_weights_repo(driver)

    feedback_history: list[dict[str, Any]] = []
    objective_weights: dict[str, float] = dict(CANONICAL_DEFAULT_WEIGHTS.weights)
    user_preference_profile: dict[str, Any] = {}

    try:
        feedback_history = await asyncio.wait_for(
            fb_repo.list_by_session(session_id),
            timeout=_TIMEOUT_SECONDS,
        )
    except (TimeoutError, Exception) as exc:
        logger.warning("load_memory: failed to load feedback history: %s", exc)

    try:
        latest_weights = await asyncio.wait_for(
            ow_repo.get_latest_for_session(session_id),
            timeout=_TIMEOUT_SECONDS,
        )
        if latest_weights and "weights" in latest_weights:
            objective_weights = latest_weights["weights"]
    except (TimeoutError, Exception) as exc:
        logger.warning("load_memory: failed to load objective weights: %s", exc)

    if callback:
        await callback("node_completed", {
            "node": "load_memory",
            "feedback_count": len(feedback_history),
            "weights_source": "session" if feedback_history else "canonical_default",
        })

    # M4b: Provenance event — only log when feedback was actually loaded
    existing_events = list(state.get("provenance_events", []))
    if feedback_history:
        existing_events.append({
            "timestamp": utc_now().isoformat(),
            "action": "feedback",
            "object_id": session_id,
            "round_number": None,
            "details": {
                "feedback_count": len(feedback_history),
                "weight_deltas": {
                    fb.get("id", ""): fb.get("weight_deltas", {})
                    for fb in feedback_history
                    if fb.get("weight_deltas")
                },
            },
        })

    return {
        "feedback_history": feedback_history,
        "objective_weights": objective_weights,
        "user_preference_profile": user_preference_profile,
        "provenance_events": existing_events,
    }
