"""Plan voicings node — generate voicing strategies and plans using Gemini Flash."""

import contextlib
import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.domain.realization.voicing import VoicingGenerator
from explorator.engine.realization_state import RealizationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import VoicingPreferences, VoicingStrategyResponse
from explorator.prompts.voicing import voicing_strategy_prompt

logger = logging.getLogger(__name__)


def _parse_json_field(data: dict[str, Any], field: str) -> Any:
    """Parse a JSON string field if stored as a string; return as-is otherwise."""
    value = data.get(field)
    if isinstance(value, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            return json.loads(value)
    return value


def _build_voicing_prefs(genre_profile: dict[str, Any]) -> VoicingPreferences:
    """Extract VoicingPreferences from a genre profile dict."""
    raw = _parse_json_field(genre_profile, "voicing_preferences")
    if isinstance(raw, dict):
        return VoicingPreferences.model_validate(raw)
    return VoicingPreferences()


def _default_strategy(prefs: VoicingPreferences) -> VoicingStrategyResponse:
    """Build a default voicing strategy from genre preferences when Gemini fails."""
    return VoicingStrategyResponse(
        global_strategy=f"{prefs.default_voicing_type} voicing, {prefs.default_register} register",
        density_level=prefs.default_density,
        voice_count=prefs.default_voice_count,
    )


async def plan_voicings(state: RealizationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Generate voicing strategies via Gemini Flash, then realize them into voicing plans."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "plan_voicings"})

    genre_profile = state.get("genre_profile", {})
    creative_brief = state.get("creative_brief", {})
    candidates_raw = state.get("progression_candidates", [])

    prefs = _build_voicing_prefs(genre_profile)
    voicing_tendencies: dict[str, str] = _parse_json_field(genre_profile, "voicing_tendencies") or {}
    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))
    key_center = creative_brief.get("key_center") or "C"
    mode = creative_brief.get("mode") or "major"

    generator = VoicingGenerator()
    all_strategies: list[dict[str, Any]] = []
    all_plans: list[dict[str, Any]] = []

    for candidate_data in candidates_raw:
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

        # Build and call LLM prompt
        user_prompt, system = voicing_strategy_prompt(
            chord_symbols=chord_symbols,
            key_center=key_center,
            mode=mode,
            genre=genre,
            voicing_tendencies=voicing_tendencies,
            voice_count=prefs.default_voice_count,
        )

        strategy: VoicingStrategyResponse
        try:
            strategy = await gemini.generate_structured(
                user_prompt,
                response_model=VoicingStrategyResponse,
                tier=ModelTier.FLASH,
                system_prompt=system,
            )
        except Exception:
            logger.warning(
                "Voicing strategy LLM call failed for candidate %s — using default",
                candidate.id,
            )
            strategy = _default_strategy(prefs)

        strategy_dict = strategy.model_dump(mode="json")
        strategy_dict["progression_candidate_id"] = candidate.id
        all_strategies.append(strategy_dict)

        # Realize into variant plans
        plans = generator.generate_variants(strategy, chord_symbols, prefs)
        for plan in plans:
            plan.progression_candidate_id = candidate.id
            all_plans.append(plan.model_dump(mode="json"))

    return {
        "voicing_strategies": all_strategies,
        "voicing_plans": all_plans,
    }
