"""Load genre node — fetch genre profile from Neo4j."""

import contextlib
import json
from typing import Any

from neo4j import AsyncDriver

from explorator.domain.style.service import StyleService
from explorator.engine.state import ExplorationState


async def load_genre(state: ExplorationState, *, driver: AsyncDriver) -> dict[str, Any]:
    """Load genre profile, grammar, and rules from Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "load_genre"})

    service = StyleService(driver)
    genre = state.get("genre", "dream_pop")

    profile = await service.get_genre_profile(genre)
    if profile is None:
        profile = {"genre": genre, "harmonic_vocabulary": [], "common_devices": []}

    # Parse JSON string fields back to dicts/lists
    for field in [
        "harmonic_tendencies",
        "voicing_tendencies",
        "bass_tendencies",
        "groove_tendencies",
        "experimentation_envelope",
    ]:
        if field in profile and isinstance(profile[field], str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                profile[field] = json.loads(profile[field])

    result = {
        "genre_profile": profile,
    }

    if callback:
        await callback("node_completed", {"node": "load_genre", "genre": genre})

    return result
