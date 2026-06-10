"""Generate bass node — deterministic bass line generation per progression candidate."""

from typing import Any

from explorator.domain.realization.bass import BassLineGenerator
from explorator.engine.state import ExplorationState
from explorator.models.groove import GroovePattern
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import BassPreferences
from explorator.utils import parse_json_field, parse_json_or_dict


def _build_bass_prefs(genre_profile: dict[str, Any]) -> BassPreferences:
    """Extract BassPreferences from a genre profile dict."""
    raw = parse_json_field(genre_profile, "bass_preferences")
    if isinstance(raw, dict):
        return BassPreferences.model_validate(raw)
    return BassPreferences()


async def generate_bass(state: ExplorationState) -> dict[str, Any]:
    """Generate deterministic bass lines for each progression candidate."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate_bass"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    creative_brief = parse_json_or_dict(state.get("creative_brief", {}))
    candidates_raw = state.get("progression_candidates", [])

    prefs = _build_bass_prefs(genre_profile)
    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))

    variant_modes = prefs.variant_bass_modes

    # Parse groove patterns for round-robin assignment
    groove_patterns_raw = state.get("groove_patterns", [])
    groove_patterns: list[GroovePattern] = []
    for gp_data in groove_patterns_raw:
        if isinstance(gp_data, dict):
            groove_patterns.append(GroovePattern.model_validate(gp_data))
        elif isinstance(gp_data, GroovePattern):
            groove_patterns.append(gp_data)

    bass_generator = BassLineGenerator()
    bass_lines: list[dict[str, Any]] = []

    for candidate_idx, candidate_data in enumerate(candidates_raw):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

        # Round-robin groove pattern assignment (None if no patterns available)
        groove_pattern = (
            groove_patterns[candidate_idx % len(groove_patterns)] if groove_patterns else None
        )

        for mode in variant_modes:
            mode_prefs = BassPreferences(
                default_bass_mode=mode,
                default_register=prefs.default_register,
                rhythmic_density=prefs.rhythmic_density,
            )
            bass_line = bass_generator.generate(
                chord_symbols, mode_prefs, genre=genre, groove_pattern=groove_pattern
            )
            bass_line.progression_candidate_id = candidate.id
            bass_lines.append(bass_line.model_dump(mode="json"))

    return {"bass_lines": bass_lines}
