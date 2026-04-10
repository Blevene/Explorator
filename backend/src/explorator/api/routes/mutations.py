"""API routes for user-initiated mutations."""

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
from explorator.domain.harmony.mutator import HarmonyMutator
from explorator.graph.repository import BaseRepository
from explorator.graph.session_repo import SessionRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mutations"])


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class TriggerMutationRequest(BaseModel):
    candidate_ids: list[str]
    guidance: str | None = None
    operations: list[str] | None = None


@router.post("/sessions/{session_id}/mutate")
async def trigger_mutation(
    session_id: str,
    request: TriggerMutationRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger user-initiated mutations on specific candidates.

    Returns 409 if a round is already in-flight for this session.
    """
    repo = SessionRepository(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not request.candidate_ids:
        raise HTTPException(status_code=422, detail="At least one candidate_id required")

    channel = SSEChannel()

    async def run_mutation() -> None:
        try:
            mutator = HarmonyMutator(gemini)
            prog_repo = ProgressionCandidateRepo(driver)
            results: list[dict[str, Any]] = []

            for cid in request.candidate_ids:
                candidate = await prog_repo.get_by_id(cid)
                if candidate is None:
                    await channel.send("mutation_error", {"error": f"Candidate {cid} not found"})
                    continue

                chord_symbols = candidate.get("chord_symbols", [])
                scores = candidate.get("metadata", {}).get("scores", {})

                response = await mutator.mutate_harmonic(
                    chord_symbols=chord_symbols,
                    genre=session.get("genre", ""),
                    scores=scores,
                    guidance=request.guidance,
                )

                results.append({
                    "source_id": cid,
                    "mutated_chord_symbols": response.mutated_chord_symbols,
                    "mutations": [m.model_dump() for m in response.mutations],
                })

            await channel.send("mutation_completed", {"results": results})
        except Exception as e:
            logger.exception("Mutation failed for session %s", session_id)
            await channel.send("mutation_error", {"error": str(e)})
        finally:
            await channel.close()

    asyncio.create_task(run_mutation())
    return EventSourceResponse(channel.stream())
