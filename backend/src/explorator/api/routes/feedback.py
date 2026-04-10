"""API route for user feedback submission."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.domain.evaluation.ranking import CANONICAL_DEFAULT_WEIGHTS
from explorator.domain.intent.feedback import FeedbackInterpreter, apply_weight_deltas
from explorator.graph.feedback_repo import FeedbackEventRepo, ObjectiveWeightsRepo
from explorator.graph.session_repo import SessionRepository
from explorator.models.evaluation import ObjectiveWeights
from explorator.models.memory import UserFeedbackEvent
from explorator.utils import utc_now

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])


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
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> FeedbackResponse:
    """Submit user feedback on a candidate. Interprets via Gemini Flash and reweights."""
    session_repo = SessionRepository(driver)
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load current weights
    ow_repo = ObjectiveWeightsRepo(driver)
    latest = await ow_repo.get_latest_for_session(session_id)
    current_weights = (
        latest["weights"]
        if latest and "weights" in latest
        else dict(CANONICAL_DEFAULT_WEIGHTS.weights)
    )

    # Get candidate scores for context
    fb_repo = FeedbackEventRepo(driver)
    candidate_scores: dict[str, float] = {}  # Best-effort; scores may not be on candidate node

    # Interpret feedback via Gemini Flash
    interpreter = FeedbackInterpreter(gemini)
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
    await fb_repo.create(event)

    # Persist new ObjectiveWeights
    existing_feedback = await fb_repo.list_by_session(session_id)
    round_n = len(existing_feedback)

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

    # Create Neo4j relationships (spec 4.6)
    async with driver.session() as neo_session:
        await neo_session.run(
            "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (c {id: $cand_id}) "
            "CREATE (fb)-[:ABOUT]->(c)",
            fb_id=feedback_id, cand_id=request.candidate_id,
        )
        await neo_session.run(
            "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (ow:ObjectiveWeights {id: $ow_id}) "
            "CREATE (fb)-[:UPDATES]->(ow)",
            fb_id=feedback_id, ow_id=weights_id,
        )
        await neo_session.run(
            "MATCH (s:Session {id: $sess_id}), (fb:UserFeedbackEvent {id: $fb_id}) "
            "CREATE (s)-[:HAS_FEEDBACK]->(fb)",
            sess_id=session_id, fb_id=feedback_id,
        )

    return FeedbackResponse(
        id=feedback_id,
        interpreted_adjustments=dict(interpretation.interpreted_adjustments),
        adjusted_weights=adjusted_weights,
        satisfaction=interpretation.satisfaction,
    )
