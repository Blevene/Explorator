"""API route for user feedback submission."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.adapters.llm import LLMClient
from explorator.api.deps import get_llm_client, get_neo4j_driver
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
from explorator.domain.intent.feedback import FeedbackInterpreter, apply_weight_deltas
from explorator.models.evaluation import ObjectiveWeights
from explorator.models.memory import UserFeedbackEvent
from explorator.persistence.factory import (
    make_feedback_event_repo,
    make_objective_weights_repo,
    make_session_repo,
)
from explorator.utils import utc_now

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])

_busy_sessions: set[str] = set()


class SubmitFeedbackRequest(BaseModel):
    candidate_id: str
    content: str
    feedback_type: str = "text_reaction"


class FeedbackResponse(BaseModel):
    id: str
    interpreted_adjustments: dict[str, Any]
    adjusted_weights: dict[str, float]
    satisfaction: str


@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(
    session_id: str,
    request: SubmitFeedbackRequest,
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> FeedbackResponse:
    """Submit user feedback on a candidate. Interprets via the flash-tier LLM and reweights.

    In memory mode (``driver is None``) feedback learning is unavailable, so this
    returns a neutral no-op (200) with the canonical default weights without
    invoking the LLM or persisting anything.
    """
    session_repo = make_session_repo(driver)
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if driver is None:
        # No durable backend: feedback re-weighting/learning is disabled. Return a
        # neutral response so the UI flow doesn't break.
        return FeedbackResponse(
            id=f"fb_{ULID()}",
            interpreted_adjustments={},
            adjusted_weights=dict(CANONICAL_DEFAULT_WEIGHTS.weights),
            satisfaction="neutral",
        )

    if session_id in _busy_sessions:
        raise HTTPException(
            status_code=409, detail="Feedback submission already in-flight for this session"
        )
    _busy_sessions.add(session_id)

    try:
        # Load current weights
        ow_repo = make_objective_weights_repo(driver)
        latest = await ow_repo.get_latest_for_session(session_id)
        current_weights = (
            latest["weights"]
            if latest and "weights" in latest
            else dict(CANONICAL_DEFAULT_WEIGHTS.weights)
        )

        # Get candidate scores for context
        fb_repo = make_feedback_event_repo(driver)
        candidate_scores: dict[str, float] = {}  # Best-effort; scores may not be on candidate node

        # Count existing feedback BEFORE creating the new one
        existing_feedback = await fb_repo.list_by_session(session_id)
        round_n = len(existing_feedback)

        # Interpret feedback via the flash-tier LLM
        interpreter = FeedbackInterpreter(llm)
        interpretation = await interpreter.interpret(
            feedback_text=request.content,
            current_weights=current_weights,
            candidate_scores=candidate_scores,
            genre=session.get("genre", ""),
        )

        # Apply weight deltas
        adjusted_weights = apply_weight_deltas(current_weights, interpretation.weight_deltas)

        # Merge satisfaction into interpreted_adjustments for persistence (spec 4.8)
        adjustments_with_satisfaction = dict(interpretation.interpreted_adjustments)
        adjustments_with_satisfaction["satisfaction"] = interpretation.satisfaction

        # Persist UserFeedbackEvent
        now = utc_now()
        feedback_id = f"fb_{ULID()}"
        event = UserFeedbackEvent(
            id=feedback_id,
            type="user_feedback_event",
            status="active",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            candidate_id=request.candidate_id,
            feedback_type=request.feedback_type,
            content=request.content,
            interpreted_adjustments=adjustments_with_satisfaction,
            weight_deltas=dict(interpretation.weight_deltas),
        )

        # Persist new ObjectiveWeights (must exist before relationship is created)
        weights_id = f"ow_{ULID()}"
        weights_entity = ObjectiveWeights(
            id=weights_id,
            type="objective_weights",
            status="active",
            created_at=now,
            updated_at=now,
            profile_name=f"session_{session_id}_round_{round_n}",
            weights=adjusted_weights,
        )
        await ow_repo.create(weights_entity)

        # Create feedback node and all relationships in a single transaction
        await fb_repo.create_with_relationships(
            event=event,
            weights_id=weights_id,
            session_id=session_id,
        )

    finally:
        _busy_sessions.discard(session_id)

    return FeedbackResponse(
        id=feedback_id,
        interpreted_adjustments=dict(interpretation.interpreted_adjustments),
        adjusted_weights=adjusted_weights,
        satisfaction=interpretation.satisfaction,
    )
