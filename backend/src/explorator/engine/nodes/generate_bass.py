"""Generate bass node — deterministic bass line generation per progression candidate."""

import contextlib
import json
import logging
from typing import Any

from explorator.domain.realization.bass import BassLineGenerator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import BassPreferences

logger = logging.getLogger(__name__)


def _parse_json_field(data: dict[str, Any], field: str) -> Any:
    """Parse a JSON string field if stored as a string; return as-is otherwise."""
    value = data.get(field)
    if isinstance(value, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            return json.loads(value)
    return value


def _build_bass_prefs(genre_profile: dict[str, Any]) -> BassPreferences:
    """Extract BassPreferences from a genre profile dict."""
    raw = _parse_json_field(genre_profile, "bass_preferences")
    if isinstance(raw, dict):
        return BassPreferences.model_validate(raw)
    return BassPreferences()


async def generate_bass(state: ExplorationState) -> dict[str, Any]:
    """Generate deterministic bass lines for each progression candidate."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_bass"})

    genre_profile = state.get("genre_profile", {})
    creative_brief = state.get("creative_brief", {})
    candidates_raw = state.get("progression_candidates", [])

    prefs = _build_bass_prefs(genre_profile)
    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))
    logger.warning("generate_bass: genre_profile bass_preferences=%s, type=%s", genre_profile.get("bass_preferences"), type(genre_profile.get("bass_preferences")).__name__)

    variant_modes = prefs.variant_bass_modes

    bass_generator = BassLineGenerator()
    bass_lines: list[dict[str, Any]] = []

    for candidate_data in candidates_raw:
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

        for mode in variant_modes:
            mode_prefs = BassPreferences(
                default_bass_mode=mode,
                default_register=prefs.default_register,
                rhythmic_density=prefs.rhythmic_density,
            )
            bass_line = bass_generator.generate(chord_symbols, mode_prefs, genre=genre)
            bass_line.progression_candidate_id = candidate.id
            bass_lines.append(bass_line.model_dump(mode="json"))

    return {"bass_lines": bass_lines}
