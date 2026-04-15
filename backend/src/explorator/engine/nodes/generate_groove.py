"""Generate groove node — deterministic groove pattern generation per progression candidate."""

import logging
from typing import Any

from explorator.domain.realization.groove import GrooveGenerator
from explorator.engine.state import ExplorationState
from explorator.models.groove import GroovePreferences
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)


async def generate_groove(state: ExplorationState) -> dict[str, Any]:
    """Generate deterministic groove patterns for each progression candidate."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_groove"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    creative_brief = parse_json_or_dict(state.get("creative_brief", {}))
    session_id = state.get("session_id", "")

    # Extract groove_tendencies from genre profile
    groove_tendencies = parse_json_or_dict(genre_profile.get("groove_tendencies", {}))
    prefs = GroovePreferences.from_genre_tendencies(groove_tendencies)

    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))

    # Use top_progressions if available, otherwise progression_candidates
    candidates_raw = state.get("top_progressions", []) or state.get("progression_candidates", [])

    # Determine variant count: 1 for sparse density, 2 otherwise
    is_sparse = prefs.comp_density in ("sparse", "low")
    variant_count = 1 if is_sparse else 2

    generator = GrooveGenerator()
    all_patterns: list[dict[str, Any]] = []

    for candidate_data in candidates_raw:
        candidate_id = candidate_data.get("id", "")
        patterns = generator.generate_variants(
            prefs,
            genre=genre,
            session_id=session_id,
            count=variant_count,
        )
        for gp in patterns:
            gp.arrangement_candidate_id = None  # will be linked in assemble
            all_patterns.append(gp.model_dump(mode="json"))

    logger.info(
        "generate_groove: produced %d patterns for %d candidates (density=%s, variants=%d)",
        len(all_patterns),
        len(candidates_raw),
        prefs.comp_density,
        variant_count,
    )

    return {"groove_patterns": [p for p in all_patterns]}
