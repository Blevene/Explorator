"""Generate node — produce progression candidates using Gemini Pro."""

from typing import Any

from explorator.adapters.gemini import GeminiClient
from explorator.domain.harmony.generator import HarmonyGenerator
from explorator.engine.state import ExplorationState
from explorator.utils import parse_json_or_dict, utc_now


async def generate(state: ExplorationState, *, gemini: GeminiClient) -> dict[str, Any]:
    """Generate N progression candidates."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "generate"})

    generator = HarmonyGenerator(gemini)
    brief = parse_json_or_dict(state.get("creative_brief", {}))
    profile = parse_json_or_dict(state.get("genre_profile", {}))

    candidates = await generator.generate(
        session_id=state["session_id"],
        genre=state.get("genre", "dream_pop"),
        key_center=brief.get("key_center", "C"),
        mode=brief.get("mode", "major"),
        bars=brief.get("phrase_length_bars", 8),
        generation_mode=state.get("generation_mode", "balanced"),
        n_candidates=state.get("n_candidates", 12),
        harmonic_vocabulary=profile.get("harmonic_vocabulary", []),
        common_devices=profile.get("common_devices", []),
        cadence_archetypes=profile.get("cadence_archetypes", []),
        mood_targets=brief.get("mood_targets", []),
    )

    serialized = [c.model_dump(mode="json") for c in candidates]

    if callback:
        await callback(
            "candidates_preview",
            {"count": len(serialized), "type": "progression"},
        )

    # M4b: Provenance event
    existing_events = list(state.get("provenance_events", []))
    existing_events.append({
        "timestamp": utc_now().isoformat(),
        "action": "generate",
        "object_id": state["session_id"],
        "round_number": state.get("round_number", 1),
        "details": {
            "candidate_count": len(serialized),
            "prompt_summary": state.get("prompt", "")[:100],
        },
    })

    return {"progression_candidates": serialized, "provenance_events": existing_events}
