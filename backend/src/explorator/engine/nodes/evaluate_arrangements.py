"""Evaluate arrangements node — run all 3 evaluators on each arrangement candidate."""

import logging
from typing import Any

from explorator.domain.evaluation.groove import GrooveEvaluator
from explorator.domain.evaluation.melody_harmony import MelodyHarmonyEvaluator
from explorator.domain.evaluation.playability import PlayabilityEvaluator
from explorator.domain.evaluation.register_density import RegisterDensityEvaluator
from explorator.domain.evaluation.voice_leading import VoiceLeadingEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.groove import GroovePattern, GroovePreferences
from explorator.models.melody import MelodicComplement
from explorator.models.realization import BassLine, VoicingPlan
from explorator.utils import parse_json_or_dict

logger = logging.getLogger(__name__)


async def evaluate_arrangements(state: ExplorationState) -> dict[str, Any]:
    """Run VoiceLeading, RegisterDensity, and Playability evaluators on each arrangement."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "evaluate_arrangements"})

    genre_profile = parse_json_or_dict(state.get("genre_profile", {}))
    voicing_prefs = parse_json_or_dict(genre_profile.get("voicing_preferences", {}))
    preferred_register: str = voicing_prefs.get("default_register", "mid")

    # Build lookups by id
    voicing_plan_lookup: dict[str, VoicingPlan] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        voicing_plan_lookup[vp.id] = vp

    bass_line_lookup: dict[str, BassLine] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        bass_line_lookup[bl.id] = bl

    # Build groove pattern lookup and preferences
    groove_pattern_lookup: dict[str, GroovePattern] = {}
    for gp_data in state.get("groove_patterns", []):
        gp = GroovePattern.model_validate(gp_data)
        groove_pattern_lookup[gp.id] = gp

    groove_tendencies = parse_json_or_dict(genre_profile.get("groove_tendencies", {}))
    groove_prefs = GroovePreferences.from_genre_tendencies(groove_tendencies)

    # Build melodic complement lookup
    melody_complement_lookup: dict[str, MelodicComplement] = {}
    for mc_data in state.get("melodic_complements", []):
        mc = MelodicComplement.model_validate(mc_data)
        melody_complement_lookup[mc.id] = mc

    # Extract melodic tendencies for motion_preference
    melodic_tendencies = parse_json_or_dict(genre_profile.get("melodic_tendencies", {}))
    motion_preference: str = melodic_tendencies.get("motion_preference", "stepwise")

    vl_evaluator = VoiceLeadingEvaluator()
    rd_evaluator = RegisterDensityEvaluator()
    play_evaluator = PlayabilityEvaluator()
    groove_evaluator = GrooveEvaluator()
    melody_evaluator = MelodyHarmonyEvaluator()

    evaluations: list[dict[str, Any]] = []

    for arr_data in state.get("arrangement_candidates", []):
        arrangement_id: str = arr_data["id"]
        voicing_plan_id: str | None = arr_data.get("voicing_plan_id")
        bass_line_id: str | None = arr_data.get("bass_line_id")

        voicing_plan = voicing_plan_lookup.get(voicing_plan_id or "")
        bass_line = bass_line_lookup.get(bass_line_id or "")

        if voicing_plan is None:
            logger.warning("No VoicingPlan found for arrangement %s — skipping", arrangement_id)
            continue

        if bass_line is None:
            logger.warning("No BassLine found for arrangement %s — skipping", arrangement_id)
            continue

        # Run evaluators
        vl_eval = vl_evaluator.evaluate(voicing_plan, candidate_id=arrangement_id)
        rd_eval = rd_evaluator.evaluate(
            voicing_plan,
            bass_line,
            candidate_id=arrangement_id,
            preferred_register=preferred_register,
        )
        play_eval = play_evaluator.evaluate(voicing_plan, candidate_id=arrangement_id)

        vl_score = vl_evaluator.overall_score(vl_eval)
        rd_score = rd_evaluator.overall_score(rd_eval)
        play_score = play_evaluator.overall_score(play_eval)

        # Groove evaluation
        groove_pattern_id: str | None = arr_data.get("groove_pattern_id")
        groove_pattern = (
            groove_pattern_lookup.get(groove_pattern_id or "") if groove_pattern_id else None
        )

        if groove_pattern is not None:
            groove_eval = groove_evaluator.evaluate(
                groove_pattern, groove_prefs, candidate_id=arrangement_id
            )
            groove_score = groove_evaluator.overall_score(groove_eval)
            groove_entry = {
                "evaluation": groove_eval.model_dump(mode="json"),
                "overall_score": groove_score,
            }
        else:
            groove_entry = {
                "evaluation": None,
                "overall_score": 5.0,
            }

        # Melody evaluation (conditional on melodic_complement_id)
        melodic_complement_id: str | None = arr_data.get("melodic_complement_id")
        melody_complement = (
            melody_complement_lookup.get(melodic_complement_id or "")
            if melodic_complement_id
            else None
        )

        if melody_complement is not None:
            # Get chord symbols from voicing events
            chord_symbols = [ve.chord_symbol for ve in voicing_plan.voicing_events]
            melody_eval = melody_evaluator.evaluate(
                complement=melody_complement,
                chord_symbols=chord_symbols,
                voicing_events=voicing_plan.voicing_events,
                motion_preference=motion_preference,
                candidate_id=arrangement_id,
            )
            melody_entry = {
                "evaluation": melody_eval.model_dump(mode="json"),
                "melody_support_score": melody_eval.melody_support_score,
                "collision_risk_score": melody_eval.collision_risk_score,
                "overall_score": melody_evaluator.overall_score(melody_eval),
            }
        else:
            melody_entry = {
                "evaluation": None,
                "melody_support_score": 5.0,
                "collision_risk_score": 5.0,
                "overall_score": 5.0,
            }

        evaluations.append(
            {
                "arrangement_candidate_id": arrangement_id,
                "voice_leading": {
                    "evaluation": vl_eval.model_dump(mode="json"),
                    "overall_score": vl_score,
                },
                "register_density": {
                    "evaluation": rd_eval.model_dump(mode="json"),
                    "overall_score": rd_score,
                },
                "playability": {
                    "evaluation": play_eval.model_dump(mode="json"),
                    "overall_score": play_score,
                },
                "groove": groove_entry,
                "melody": melody_entry,
            }
        )

    return {"evaluations": evaluations}
