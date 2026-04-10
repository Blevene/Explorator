"""Evaluate arrangements node — run all 3 evaluators on each arrangement candidate."""

import logging
from typing import Any

from explorator.domain.evaluation.playability import PlayabilityEvaluator
from explorator.domain.evaluation.register_density import RegisterDensityEvaluator
from explorator.domain.evaluation.voice_leading import VoiceLeadingEvaluator
from explorator.engine.state import ExplorationState
from explorator.models.realization import BassLine, VoicingPlan

logger = logging.getLogger(__name__)


async def evaluate_arrangements(state: ExplorationState) -> dict[str, Any]:
    """Run VoiceLeading, RegisterDensity, and Playability evaluators on each arrangement."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "evaluate_arrangements"})

    genre_profile = state.get("genre_profile", {})
    preferred_register: str = (
        genre_profile.get("voicing_preferences", {}).get("default_register", "mid")
    )

    # Build lookups by id
    voicing_plan_lookup: dict[str, VoicingPlan] = {}
    for vp_data in state.get("voicing_plans", []):
        vp = VoicingPlan.model_validate(vp_data)
        voicing_plan_lookup[vp.id] = vp

    bass_line_lookup: dict[str, BassLine] = {}
    for bl_data in state.get("bass_lines", []):
        bl = BassLine.model_validate(bl_data)
        bass_line_lookup[bl.id] = bl

    vl_evaluator = VoiceLeadingEvaluator()
    rd_evaluator = RegisterDensityEvaluator()
    play_evaluator = PlayabilityEvaluator()

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
            voicing_plan, bass_line, candidate_id=arrangement_id,
            preferred_register=preferred_register,
        )
        play_eval = play_evaluator.evaluate(voicing_plan, candidate_id=arrangement_id)

        vl_score = vl_evaluator.overall_score(vl_eval)
        rd_score = rd_evaluator.overall_score(rd_eval)
        play_score = play_evaluator.overall_score(play_eval)

        evaluations.append({
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
        })

    return {"evaluations": evaluations}
