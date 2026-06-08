"""Round triggering and SSE progress endpoints."""

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
from explorator.engine.graph import build_exploration_graph
from explorator.persistence.factory import make_session_repo
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rounds"])

# Single, non-configurable generation profile: conservative breadth (8 candidates,
# top 3 selected) with a 2-round guided-search budget. Keeps real-Gemini rounds
# fast enough to finish within the client timeout.
N_CANDIDATES = 8
K_SELECTION = 3
MAX_ROUNDS = 2


class TriggerRoundRequest(BaseModel):
    prompt: str | None = None
    genre: str | None = None


class RoundResponse(BaseModel):
    round_id: str
    status: str


@router.post("/sessions/{session_id}/rounds")
async def trigger_round(
    session_id: str,
    request: TriggerRoundRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a generation round and stream progress via SSE."""
    # Verify session exists
    repo = make_session_repo(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Resolve genre and mood. The explicit request value wins, then the stored
    # session metadata, then a sane default. The engine's parser still needs a
    # non-empty prompt for context, so an empty mood falls back to the genre.
    metadata = parse_json_or_dict(session.get("metadata"))
    session_genre = metadata.get("genre", "")
    session_prompt = metadata.get("prompt", "")
    genre = request.genre or session_genre or "dream_pop"
    mood = request.prompt or session_prompt or ""
    prompt = mood or genre

    # Persist in-session genre/mood switches so reload sticks.
    if request.genre and request.genre != session_genre:
        new_metadata = dict(metadata)
        new_metadata["genre"] = request.genre
        if request.prompt:
            new_metadata["prompt"] = request.prompt
        await repo.update_metadata(session_id, new_metadata)

    channel = SSEChannel()
    graph = build_exploration_graph(gemini, driver)

    initial_state: dict[str, Any] = {
        "session_id": session_id,
        "prompt": prompt,
        "genre": genre,
        "generation_mode": "conservative",
        "round_number": 1,
        "n_candidates": N_CANDIDATES,
        "k_selection": K_SELECTION,
        "search_plan": {"stop_conditions": {"max_rounds": MAX_ROUNDS}},
        "on_progress": channel.send,
        "provenance_events": [],
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state, {"recursion_limit": 100})
        except Exception as e:
            logger.exception("Round failed for session %s", session_id)
            await channel.send("round_error", {"error": str(e)})
        finally:
            await channel.close()

    # Start the round in the background
    asyncio.create_task(run_and_close())

    return EventSourceResponse(channel.stream())
