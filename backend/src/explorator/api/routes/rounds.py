"""Round triggering and SSE progress endpoints."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.gemini import GeminiClient
from explorator.api.deps import get_gemini_client, get_neo4j_driver
from explorator.api.sse import SSEChannel
from explorator.engine.graph import build_m1_graph
from explorator.graph.session_repo import SessionRepository

router = APIRouter(tags=["rounds"])

# Generation mode → (n_candidates, k_selection)
MODE_PARAMS: dict[str, tuple[int, int]] = {
    "conservative": (8, 3),
    "balanced": (12, 4),
    "exploratory": (16, 6),
}


class TriggerRoundRequest(BaseModel):
    prompt: str | None = None
    generation_mode: str = "balanced"


class RoundResponse(BaseModel):
    round_id: str
    status: str


@router.post("/sessions/{session_id}/rounds")
async def trigger_round(
    session_id: str,
    request: TriggerRoundRequest,
    gemini: GeminiClient = Depends(get_gemini_client),  # noqa: B008
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> EventSourceResponse:
    """Trigger a generation round and stream progress via SSE."""
    # Verify session exists
    repo = SessionRepository(driver)
    session = await repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Resolve prompt: use request prompt or fall back to session's stored prompt
    metadata = session.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    session_prompt = metadata.get("prompt", "") if isinstance(metadata, dict) else ""
    prompt = request.prompt or session_prompt

    channel = SSEChannel()
    graph = build_m1_graph(gemini, driver)

    n, k = MODE_PARAMS.get(request.generation_mode, (12, 4))

    initial_state = {
        "session_id": session_id,
        "prompt": prompt,
        "generation_mode": request.generation_mode,
        "round_number": 1,
        "n_candidates": n,
        "k_selection": k,
        "on_progress": channel.send,
    }

    async def run_and_close() -> None:
        try:
            await graph.ainvoke(initial_state)
        except Exception as e:
            await channel.send("round_error", {"error": str(e)})
        finally:
            await channel.close()

    # Start the round in the background
    asyncio.create_task(run_and_close())

    return EventSourceResponse(channel.stream())
