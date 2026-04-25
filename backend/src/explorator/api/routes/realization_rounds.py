"""API routes for triggering realization rounds and querying arrangements."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.engine.graph import build_realization_subgraph
from explorator.graph.arrangement_candidate_repo import (
    ArrangementCandidateRepo as ArrangementCandidateGraphRepo,
)
from explorator.graph.repository import BaseRepository
from explorator.graph.session_repo import SessionRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realization"])


class TriggerRealizationRequest(BaseModel):
    progression_candidate_ids: list[str]


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"


class ScorecardRepo(BaseRepository):
    label = "AggregateScorecard"


@router.post("/sessions/{session_id}/realization-rounds")
async def trigger_realization(
    session_id: str,
    request: TriggerRealizationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a realization round and stream progress via SSE."""
    repo = SessionRepository(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not request.progression_candidate_ids:
        raise HTTPException(
            status_code=422, detail="At least one progression_candidate_id required"
        )

    channel = SSEChannel()
    graph = build_realization_subgraph(gemini, driver)

    initial_state = {
        "session_id": session_id,
        "progression_candidate_ids": request.progression_candidate_ids,
        "on_progress": channel.send,
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state, {"recursion_limit": 100})
        except ValueError as e:
            await channel.send("realization_error", {"error": str(e)})
        except Exception as e:
            logger.exception("Realization round failed for session %s", session_id)
            await channel.send("realization_error", {"error": str(e)})
        finally:
            await channel.close()

    asyncio.create_task(run_and_close())
    return EventSourceResponse(channel.stream())


@router.get("/candidates/{candidate_id}/arrangements")
async def list_arrangements(
    candidate_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> list[dict[str, Any]]:
    """List arrangement candidates for a progression candidate."""
    repo = ArrangementCandidateRepo(driver)
    results = await repo.query_by_property("progression_candidate_id", candidate_id)

    sc_repo = ScorecardRepo(driver)
    for r in results:
        scorecards = await sc_repo.query_by_property("candidate_id", r.get("id"))
        if scorecards:
            sc = scorecards[0]
            r["weighted_total"] = sc.get("weighted_total", 0.0)
            r["rank_within_round"] = sc.get("rank_within_round", 0)

    # Batch-derive curation state for all returned arrangements in one query.
    graph_repo = ArrangementCandidateGraphRepo(driver)
    arr_ids = [r["id"] for r in results if r.get("id")]
    curation = await graph_repo.fetch_curation_state(arr_ids)
    for r in results:
        is_curated, curated_at = curation.get(r.get("id") or "", (None, None))
        r["is_curated"] = is_curated
        r["curated_at"] = curated_at

    return results


@router.get("/arrangements/{arrangement_id}")
async def get_arrangement(
    arrangement_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, Any]:
    """Get a single arrangement with its voicing plan and bass line."""
    from explorator.graph.bass_line_repo import BassLineRepo
    from explorator.graph.groove_pattern_repo import GroovePatternRepo
    from explorator.graph.melodic_complement_repo import MelodicComplementRepo
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo

    ac_repo = ArrangementCandidateRepo(driver)
    arrangement = await ac_repo.get_by_id(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="Arrangement not found")

    vp_id = arrangement.get("voicing_plan_id")
    bl_id = arrangement.get("bass_line_id")
    gp_id = arrangement.get("groove_pattern_id")
    if vp_id:
        arrangement["voicing_plan"] = await VoicingPlanRepo(driver).get_by_id(vp_id)
    if bl_id:
        arrangement["bass_line"] = await BassLineRepo(driver).get_by_id(bl_id)
    if gp_id:
        arrangement["groove_pattern"] = await GroovePatternRepo(driver).get_by_id(gp_id)

    mc_id = arrangement.get("melodic_complement_id")
    if mc_id:
        arrangement["melodic_complement"] = await MelodicComplementRepo(driver).get_by_id(mc_id)

    sc_repo = ScorecardRepo(driver)
    scorecards = await sc_repo.query_by_property("candidate_id", arrangement_id)
    if scorecards:
        arrangement["scorecard"] = scorecards[0]

    # Curation state derivation (M5d-3). Nullable; see spec.
    graph_repo = ArrangementCandidateGraphRepo(driver)
    curation = await graph_repo.fetch_curation_state([arrangement_id])
    is_curated, curated_at = curation.get(arrangement_id, (None, None))
    arrangement["is_curated"] = is_curated
    arrangement["curated_at"] = curated_at

    return arrangement
