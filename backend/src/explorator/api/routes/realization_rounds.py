"""API routes for triggering realization rounds and querying arrangements."""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.llm import LLMClient
from explorator.api.deps import get_llm_client, get_neo4j_driver
from explorator.api.sse import SSEChannel, cancel_on_disconnect
from explorator.engine.graph import build_realization_subgraph
from explorator.persistence.factory import (
    make_arrangement_candidate_repo,
    make_scorecard_repo,
    make_session_repo,
)
from explorator.utils import (
    normalize_key_and_mode,
    resolve_session_genre,
    resolve_session_key,
    resolve_session_mode,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realization"])


class TriggerRealizationRequest(BaseModel):
    progression_candidate_ids: list[str]
    key: str | None = None
    musical_mode: str | None = None


@router.post("/sessions/{session_id}/realization-rounds")
async def trigger_realization(
    session_id: str,
    request: TriggerRealizationRequest,
    gemini: LLMClient = Depends(get_llm_client),  # noqa: B008
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a realization round and stream progress via SSE."""
    repo = make_session_repo(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not request.progression_candidate_ids:
        raise HTTPException(
            status_code=422, detail="At least one progression_candidate_id required"
        )

    channel = SSEChannel()
    graph = build_realization_subgraph(gemini, driver)

    # Resolve the session's genre from its metadata so load_context loads the
    # correct genre profile. In memory mode persist_round never writes
    # `Session.genre` and no CreativeBrief is persisted, so without this the
    # load_context fallback chain would default to "dream_pop".
    genre = resolve_session_genre(session)

    # Effective key + musical mode: request override → session metadata →
    # default, normalized so a bad value never crashes generation.
    key, musical_mode = normalize_key_and_mode(
        request.key or resolve_session_key(session),
        request.musical_mode or resolve_session_mode(session),
    )

    initial_state = {
        "session_id": session_id,
        "progression_candidate_ids": request.progression_candidate_ids,
        "genre": genre,
        "key_center": key,
        "mode": musical_mode,
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

    # Cancel the detached round if the client disconnects before it finishes.
    task = asyncio.create_task(run_and_close())
    return EventSourceResponse(cancel_on_disconnect(channel, task))


@router.get("/candidates/{candidate_id}/arrangements")
async def list_arrangements(
    candidate_id: str,
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> list[dict[str, Any]]:
    """List arrangement candidates for a progression candidate."""
    repo = make_arrangement_candidate_repo(driver)
    results = await repo.query_by_property("progression_candidate_id", candidate_id)

    sc_repo = make_scorecard_repo(driver)
    for r in results:
        scorecards = await sc_repo.query_by_property("candidate_id", r.get("id"))
        if scorecards:
            sc = scorecards[0]
            r["weighted_total"] = sc.get("weighted_total", 0.0)
            r["rank_within_round"] = sc.get("rank_within_round", 0)

    # Batch-derive curation state for all returned arrangements. Memory mode
    # returns (None, None) per id.
    arr_ids = [r["id"] for r in results if r.get("id")]
    curation = await repo.fetch_curation_state(arr_ids)
    for r in results:
        is_curated, curated_at = curation.get(r.get("id") or "", (None, None))
        r["is_curated"] = is_curated
        r["curated_at"] = curated_at

    return results


@router.get("/arrangements/{arrangement_id}")
async def get_arrangement(
    arrangement_id: str,
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, Any]:
    """Get a single arrangement with its voicing plan and bass line."""
    from explorator.persistence.factory import (
        make_bass_line_repo,
        make_groove_pattern_repo,
        make_melodic_complement_repo,
        make_voicing_plan_repo,
    )

    ac_repo = make_arrangement_candidate_repo(driver)
    arrangement = await ac_repo.get_by_id(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="Arrangement not found")

    vp_id = arrangement.get("voicing_plan_id")
    bl_id = arrangement.get("bass_line_id")
    gp_id = arrangement.get("groove_pattern_id")
    if vp_id:
        arrangement["voicing_plan"] = await make_voicing_plan_repo(driver).get_by_id(vp_id)
    if bl_id:
        arrangement["bass_line"] = await make_bass_line_repo(driver).get_by_id(bl_id)
    if gp_id:
        arrangement["groove_pattern"] = await make_groove_pattern_repo(driver).get_by_id(gp_id)

    mc_id = arrangement.get("melodic_complement_id")
    if mc_id:
        arrangement["melodic_complement"] = await make_melodic_complement_repo(
            driver
        ).get_by_id(mc_id)

    sc_repo = make_scorecard_repo(driver)
    scorecards = await sc_repo.query_by_property("candidate_id", arrangement_id)
    if scorecards:
        arrangement["scorecard"] = scorecards[0]

    # Curation state derivation (M5d-3). Nullable; memory mode returns
    # (None, None) so the arrangement is still returned with curation null.
    curation = await ac_repo.fetch_curation_state([arrangement_id])
    is_curated, curated_at = curation.get(arrangement_id, (None, None))
    arrangement["is_curated"] = is_curated
    arrangement["curated_at"] = curated_at

    return arrangement
