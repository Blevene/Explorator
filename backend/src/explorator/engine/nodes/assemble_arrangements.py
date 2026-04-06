"""Assemble arrangements node — combine voicing plans and bass lines into arrangement candidates."""

from typing import Any

from explorator.domain.realization.assembly import ArrangementAssembler
from explorator.engine.realization_state import RealizationState
from explorator.models.realization import BassLine, VoicingPlan


async def assemble_arrangements(state: RealizationState) -> dict[str, Any]:
    """Group voicing plans and bass lines by progression candidate, then assemble families."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "assemble_arrangements"})

    session_id = state.get("session_id", "")
    creative_brief = state.get("creative_brief", {})
    voicing_plans_raw = state.get("voicing_plans", [])
    bass_lines_raw = state.get("bass_lines", [])

    # Intent tags come from creative brief mood targets
    intent_tags: list[str] = creative_brief.get("mood_targets", [])

    # Group voicing plans by progression_candidate_id
    plans_by_candidate: dict[str, list[VoicingPlan]] = {}
    for vp_data in voicing_plans_raw:
        vp = VoicingPlan.model_validate(vp_data)
        cid = vp.progression_candidate_id or ""
        plans_by_candidate.setdefault(cid, []).append(vp)

    # Map bass lines by progression_candidate_id (one per candidate)
    bass_by_candidate: dict[str, BassLine] = {}
    for bl_data in bass_lines_raw:
        bl = BassLine.model_validate(bl_data)
        cid = bl.progression_candidate_id or ""
        bass_by_candidate[cid] = bl

    assembler = ArrangementAssembler()
    all_candidates: list[dict[str, Any]] = []
    all_families: list[dict[str, Any]] = []

    for candidate_id, voicing_plans in plans_by_candidate.items():
        bass_line = bass_by_candidate.get(candidate_id)
        if bass_line is None or not voicing_plans:
            continue

        family, candidates = assembler.assemble_family(
            progression_candidate_id=candidate_id,
            session_id=session_id,
            voicing_plans=voicing_plans,
            bass_line=bass_line,
            intent_tags=intent_tags,
        )
        all_families.append(family.model_dump(mode="json"))
        all_candidates.extend(c.model_dump(mode="json") for c in candidates)

    return {
        "arrangement_candidates": all_candidates,
        "arrangement_families": all_families,
    }
