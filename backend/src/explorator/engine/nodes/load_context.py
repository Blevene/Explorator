"""Load context node — fetch progression candidates, genre profile, and creative brief."""

import logging
from typing import Any

from neo4j import AsyncDriver

from explorator.engine.realization_state import RealizationState
from explorator.graph.repository import BaseRepository

logger = logging.getLogger(__name__)


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class SessionRepo(BaseRepository):
    label = "Session"


class GenreProfileRepo(BaseRepository):
    label = "GenreProfile"

    async def get_by_genre(self, genre: str) -> dict[str, Any] | None:
        """Fetch a genre profile by its genre name field."""
        results = await self.query_by_property("genre", genre)
        return results[0] if results else None


class CreativeBriefRepo(BaseRepository):
    label = "CreativeBrief"

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        """Fetch the creative brief associated with a session."""
        results = await self.query_by_property("session_id", session_id)
        return results[0] if results else None


async def load_context(state: RealizationState, *, driver: AsyncDriver) -> dict[str, Any]:
    """Fetch progression candidates, session, genre profile, and creative brief from Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_context"})

    candidate_ids = state.get("progression_candidate_ids", [])

    candidate_repo = ProgressionCandidateRepo(driver)
    session_repo = SessionRepo(driver)
    genre_profile_repo = GenreProfileRepo(driver)
    brief_repo = CreativeBriefRepo(driver)

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

    # Fetch session to get genre name (persisted by M1 persist_round)
    session_data = await session_repo.get_by_id(session_id)
    genre = ""
    if session_data:
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

    # Fetch genre profile
    genre_profile: dict[str, Any] = {}
    if genre:
        gp = await genre_profile_repo.get_by_genre(genre)
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
