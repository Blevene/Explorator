"""Plan voicings node — generate voicing strategies and plans using Gemini Flash."""

import asyncio
import logging
from typing import Any

from pydantic import ValidationError

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.domain.realization.voicing import VoicingGenerator
from explorator.engine.state import ExplorationState
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import (
    ChordVoicingInstruction,
    VoicingPreferences,
    VoicingStrategyResponse,
)
from explorator.prompts.voicing import voicing_strategy_prompt
from explorator.utils import parse_json_field, parse_json_or_dict

logger = logging.getLogger(__name__)


# The genre catalog (esp. LLM-generated genres) uses a richer voicing vocabulary
# than the VoicingPreferences model's Literal types. Map catalog terms onto the
# supported set so a genre's voicing block can never crash a round; unknown
# values fall back to the field default (and unknown variant entries are dropped).
_VOICING_TYPE_MAP = {
    "open": "open", "close": "close", "closed": "close",
    "drop2": "drop2", "drop3": "drop3",
    "cluster": "close", "quartal": "open",
}
_DENSITY_MAP = {
    "thin": "thin", "sparse": "thin", "low": "thin",
    "medium": "medium", "low_medium": "medium", "moderate": "medium",
    "full": "full", "high": "full", "dense": "full", "active": "full",
}
_REGISTER_MAP = {
    "low": "low", "mid": "mid", "middle": "mid", "medium": "mid",
    "mid_high": "mid_high", "high": "high",
}


def _norm(value: Any, mapping: dict[str, str], default: str | None) -> str | None:
    """Map a catalog term onto a supported literal, or `default` if unknown."""
    if not isinstance(value, str):
        return default
    return mapping.get(value.strip().lower().replace("-", "_"), default)


def _build_voicing_prefs(genre_profile: dict[str, Any]) -> VoicingPreferences:
    """Extract VoicingPreferences from a genre profile dict, tolerant of the
    catalog's extended vocabulary (sparse/dense/high density, closed/cluster/
    quartal voicings, etc.)."""
    raw = parse_json_field(genre_profile, "voicing_preferences")
    if not isinstance(raw, dict):
        return VoicingPreferences()

    data = dict(raw)
    for field, mapping, default in (
        ("default_voicing_type", _VOICING_TYPE_MAP, "open"),
        ("default_density", _DENSITY_MAP, "medium"),
        ("default_register", _REGISTER_MAP, "mid"),
    ):
        if field in data:
            data[field] = _norm(data[field], mapping, default)
    if isinstance(data.get("variant_voicing_types"), list):
        normalized: list[str] = []
        for v in data["variant_voicing_types"]:
            mapped = _norm(v, _VOICING_TYPE_MAP, None)
            if mapped is not None and mapped not in normalized:
                normalized.append(mapped)
        data["variant_voicing_types"] = normalized or ["open", "drop2", "close"]

    try:
        return VoicingPreferences.model_validate(data)
    except ValidationError:
        logger.warning("Unparseable voicing_preferences; using defaults", exc_info=True)
        return VoicingPreferences()


def _default_strategy(
    prefs: VoicingPreferences,
    chord_symbols: list[str] | None = None,
) -> VoicingStrategyResponse:
    """Build a default voicing strategy from genre preferences when Gemini fails.

    When chord_symbols are provided, generates per-chord instructions with
    genre-appropriate extensions (7th for triads) to avoid wasting voices.
    """
    per_chord = []
    if chord_symbols:
        for symbol in chord_symbols:
            # If the chord symbol doesn't already contain '7', '9', '11', '13',
            # suggest adding a 7th to fill the voice count
            has_extension = any(ext in symbol for ext in ("7", "9", "11", "13"))
            extensions = [] if has_extension else ["7"]
            per_chord.append(
                ChordVoicingInstruction(
                    chord_symbol=symbol,
                    voicing_type=prefs.default_voicing_type,
                    target_register=prefs.default_register,
                    extensions_to_include=extensions,
                )
            )

    return VoicingStrategyResponse(
        global_strategy=f"{prefs.default_voicing_type} voicing, {prefs.default_register} register",
        density_level=prefs.default_density,
        voice_count=prefs.default_voice_count,
        per_chord=per_chord,
    )


async def plan_voicings(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Generate voicing strategies via Gemini Flash, then realize them into voicing plans."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "plan_voicings"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    creative_brief = parse_json_or_dict(state.get("creative_brief", {}))
    candidates_raw = state.get("progression_candidates", [])

    prefs = _build_voicing_prefs(genre_profile)
    voicing_tendencies: dict[str, str] = parse_json_field(genre_profile, "voicing_tendencies") or {}
    genre = genre_profile.get("genre", creative_brief.get("genre", "dream_pop"))
    key_center = creative_brief.get("key_center") or "C"
    mode = creative_brief.get("mode") or "major"

    generator = VoicingGenerator()

    async def _process_candidate(
        candidate_data: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Process one candidate: LLM strategy → voicing plan variants."""
        candidate = ProgressionCandidate.model_validate(candidate_data)
        chord_symbols = [e.symbol for e in candidate.chord_events]

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
            strategy = _default_strategy(prefs, chord_symbols)

        strategy_dict = strategy.model_dump(mode="json")
        strategy_dict["progression_candidate_id"] = candidate.id

        plans_out: list[dict[str, Any]] = []
        for plan in generator.generate_variants(strategy, chord_symbols, prefs):
            plan.progression_candidate_id = candidate.id
            plans_out.append(plan.model_dump(mode="json"))

        return strategy_dict, plans_out

    # Run all candidates in parallel
    results = await asyncio.gather(
        *[_process_candidate(cd) for cd in candidates_raw],
        return_exceptions=True,
    )

    all_strategies: list[dict[str, Any]] = []
    all_plans: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("Voicing generation failed for a candidate: %s", r)
            continue
        strategy_dict, plans_out = r
        all_strategies.append(strategy_dict)
        all_plans.extend(plans_out)

    return {
        "voicing_strategies": all_strategies,
        "voicing_plans": all_plans,
    }
