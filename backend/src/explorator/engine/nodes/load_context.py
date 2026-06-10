"""Load context node — fetch progression candidates, genre profile, and creative brief."""

import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.style.service import StyleService
from explorator.engine.state import ExplorationState
from explorator.persistence.factory import (
    make_candidate_repo,
    make_creative_brief_repo,
    make_session_repo,
)

logger = logging.getLogger(__name__)


async def load_context(
    state: ExplorationState, *, driver: AsyncDriver | None
) -> dict[str, Any]:
    """Fetch progression candidates, session, genre profile, and creative brief from Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_context"})

    # In unified graph, M1 nodes already populated these fields.
    # Skip Neo4j fetch when progression_candidates is present — if M1 ran,
    # genre_profile and creative_brief are guaranteed to be in state too.
    if state.get("progression_candidates"):
        return {}

    candidate_ids = state.get("progression_candidate_ids", [])

    candidate_repo = make_candidate_repo(driver)
    session_repo = make_session_repo(driver)
    style_service = StyleService(driver)
    brief_repo = make_creative_brief_repo(driver)

    # Fetch all progression candidates
    candidates: list[dict[str, Any]] = []
    for cid in candidate_ids:
        data = await candidate_repo.get_by_id(cid)
        if data is None:
            raise ValueError(f"ProgressionCandidate not found: {cid}")
        candidates.append(data)

    # Derive session_id from first candidate
    if not candidates:
        raise ValueError("No progression candidate IDs provided")
    session_id = candidates[0].get("session_id", "")

    # Prefer the genre carried on state (set by the realization trigger route
    # from session metadata, or by rounds.py in the combined flow). This is the
    # only reliable source in memory mode, where persist_round skips the
    # `Session.genre` write and no CreativeBrief is persisted.
    genre = state.get("genre", "")
    # Fetch session to get genre name (persisted by M1 persist_round)
    session_data = await session_repo.get_by_id(session_id)
    if not genre and session_data:
        genre = session_data.get("genre", "")
    # Fallback chain: creative brief → candidate metadata → default
    if not genre:
        brief_data = await brief_repo.get_by_session_id(session_id)
        if brief_data:
            genre = brief_data.get("genre", "")
    if not genre:
        for c in candidates:
            meta = c.get("metadata", {})
            if isinstance(meta, dict) and meta.get("genre"):
                genre = meta["genre"]
                break
    if not genre:
        logger.warning("No genre found for session %s — defaulting to dream_pop", session_id)
        genre = "dream_pop"

    # Fetch genre profile via StyleService — Neo4j mode runs the same
    # `MATCH (n:GenreProfile {genre: $genre})` lookup the inline GenreProfileRepo
    # used; memory mode serves the equivalent profile straight from YAML.
    genre_profile: dict[str, Any] = {}
    if genre:
        gp = await style_service.get_genre_profile(genre)
        if gp:
            genre_profile = gp

    # Fetch creative brief by session_id
    creative_brief: dict[str, Any] = {}
    brief_data = await brief_repo.get_by_session_id(session_id)
    if brief_data:
        creative_brief = brief_data

    return {
        "session_id": session_id,
        "progression_candidates": candidates,
        "genre_profile": genre_profile,
        "creative_brief": creative_brief,
    }
