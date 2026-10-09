"""Round triggering and SSE progress endpoints."""

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from explorator.adapters.llm import LLMClient
from explorator.adapters.usage import track_usage
from explorator.api.deps import get_llm_client, get_neo4j_driver
from explorator.api.sse import SSEChannel, cancel_on_disconnect
from explorator.engine.graph import build_exploration_graph
from explorator.persistence.factory import make_session_repo
from explorator.utils import (
    DEFAULT_KEY,
    DEFAULT_MODE,
    normalize_key_and_mode,
    parse_json_or_dict,
)

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
    key: str | None = None
    musical_mode: str | None = None


class RoundResponse(BaseModel):
    round_id: str
    status: str


@router.post("/sessions/{session_id}/rounds")
async def trigger_round(
    session_id: str,
    request: TriggerRoundRequest,
    gemini: LLMClient = Depends(get_llm_client),  # noqa: B008
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

    # Resolve effective key + musical mode: request override → session metadata
    # → default, then normalize so a bad value never crashes generation.
    session_key = metadata.get("key", DEFAULT_KEY)
    session_mode = metadata.get("musical_mode", DEFAULT_MODE)
    key, musical_mode = normalize_key_and_mode(
        request.key or session_key, request.musical_mode or session_mode
    )

    # Persist in-session genre/mood/key/mode switches so reload sticks. Symmetric
    # on all fields: a round that changes only one with the same others must
    # still persist the new value.
    genre_changed = bool(request.genre) and request.genre != session_genre
    prompt_changed = bool(request.prompt) and request.prompt != session_prompt
    key_changed = bool(request.key) and key != session_key
    mode_changed = bool(request.musical_mode) and musical_mode != session_mode
    if genre_changed or prompt_changed or key_changed or mode_changed:
        new_metadata = dict(metadata)
        if request.genre:
            new_metadata["genre"] = request.genre
        if request.prompt:
            new_metadata["prompt"] = request.prompt
        if request.key:
            new_metadata["key"] = key
        if request.musical_mode:
            new_metadata["musical_mode"] = musical_mode
        await repo.update_metadata(session_id, new_metadata)

    channel = SSEChannel()
    graph = build_exploration_graph(gemini, driver)

    initial_state: dict[str, Any] = {
        "session_id": session_id,
        "prompt": prompt,
        "genre": genre,
        "key_center": key,
        "mode": musical_mode,
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
            with track_usage() as round_usage:
                try:
                    await graph.ainvoke(initial_state, {"recursion_limit": 100})
                finally:
                    # Tokens are billed even on a failed/partial round, so always
                    # report spend before surfacing any error. Best-effort: a send
                    # failure here must not mask the original exception. (Suppresses
                    # Exception only — CancelledError is BaseException and still
                    # propagates, so client-disconnect cancellation is unaffected.)
                    total = round_usage.totals()["total"]
                    if total == 0:
                        logger.warning(
                            "Round for session %s recorded zero token usage — "
                            "instrumentation may be misconfigured", session_id,
                        )
                    with contextlib.suppress(Exception):
                        await channel.send(
                            "token_usage",
                            round_usage.to_event(initial_state.get("round_number", 1)),
                        )
        except Exception as e:
            logger.exception("Round failed for session %s", session_id)
            await channel.send("round_error", {"error": str(e)})
        finally:
            await channel.close()

    # Start the round in the background, but cancel it if the client disconnects
    # before it finishes (otherwise graph.ainvoke + its Gemini spend run to
    # completion against a stream nobody is reading).
    task = asyncio.create_task(run_and_close())

    return EventSourceResponse(cancel_on_disconnect(channel, task))
