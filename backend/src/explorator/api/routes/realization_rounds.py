"""API routes for triggering realization rounds and querying arrangements."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.engine.realization_graph import build_realization_graph
from explorator.graph.repository import BaseRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realization"])


class TriggerRealizationRequest(BaseModel):
    progression_candidate_ids: list[str]


class SessionRepo(BaseRepository):
    label = "Session"


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"


@router.post("/sessions/{session_id}/realization-rounds")
async def trigger_realization(
    session_id: str,
    request: TriggerRealizationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver=Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a realization round and stream progress via SSE."""
    repo = SessionRepo(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not request.progression_candidate_ids:
        raise HTTPException(status_code=422, detail="At least one progression_candidate_id required")

    channel = SSEChannel()
    graph = build_realization_graph(gemini, driver)

    initial_state = {
        "session_id": session_id,
        "progression_candidate_ids": request.progression_candidate_ids,
        "on_progress": channel.send,
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state)
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
async def list_arrangements(candidate_id: str, driver=Depends(get_neo4j_driver)) -> list[dict[str, Any]]:  # noqa: B008
    """List arrangement candidates for a progression candidate."""
    repo = ArrangementCandidateRepo(driver)
    return await repo.query_by_property("progression_candidate_id", candidate_id)


@router.get("/arrangements/{arrangement_id}")
async def get_arrangement(arrangement_id: str, driver=Depends(get_neo4j_driver)) -> dict[str, Any]:  # noqa: B008
    """Get a single arrangement with its voicing plan and bass line."""
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo
    from explorator.graph.bass_line_repo import BassLineRepo

    ac_repo = ArrangementCandidateRepo(driver)
    arrangement = await ac_repo.get_by_id(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="Arrangement not found")

    vp_id = arrangement.get("voicing_plan_id")
    bl_id = arrangement.get("bass_line_id")
    if vp_id:
        arrangement["voicing_plan"] = await VoicingPlanRepo(driver).get_by_id(vp_id)
    if bl_id:
        arrangement["bass_line"] = await BassLineRepo(driver).get_by_id(bl_id)

    return arrangement
