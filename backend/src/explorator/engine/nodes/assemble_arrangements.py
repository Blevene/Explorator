"""Assemble arrangements node — combine voicing plans and bass lines into arrangement candidates."""

from typing import Any

from ulid import ULID

from explorator.domain.realization.assembly import ArrangementAssembler
from explorator.engine.state import ExplorationState
from explorator.models.realization import ArrangementFamily, BassLine, VoicingPlan
from explorator.utils import utc_now


async def assemble_arrangements(state: ExplorationState) -> dict[str, Any]:
    """Group voicing plans and bass lines by progression candidate, then assemble families.

    M2b: each progression may have multiple bass lines (one per variant mode).  The
    assembly creates one ArrangementCandidate for every (VoicingPlan × BassLine)
    combination and collects them all into a single ArrangementFamily per progression.
    """
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "assemble"})

    session_id = state.get("session_id", "")
    creative_brief = state.get("creative_brief", {})
    voicing_plans_raw = state.get("voicing_plans", [])
    bass_lines_raw = state.get("bass_lines", [])

    # Intent tags come from creative brief mood targets
    intent_tags: list[str] = creative_brief.get("mood_targets", [])

    # Group voicing plans by progression_candidate_id
    vp_by_prog: dict[str, list[VoicingPlan]] = {}
    for vp_data in voicing_plans_raw:
        vp = VoicingPlan.model_validate(vp_data)
        cid = vp.progression_candidate_id or ""
        vp_by_prog.setdefault(cid, []).append(vp)

    # Group bass lines by progression_candidate_id (multiple per candidate in M2b)
    bls_by_prog: dict[str, list[BassLine]] = {}
    for bl_data in bass_lines_raw:
        bl = BassLine.model_validate(bl_data)
        pid = bl.progression_candidate_id or ""
        bls_by_prog.setdefault(pid, []).append(bl)

    assembler = ArrangementAssembler()
    all_candidates: list[dict[str, Any]] = []
    all_families: list[dict[str, Any]] = []

    # Iterate over all known progression IDs from voicing plans
    for candidate_id, plans in vp_by_prog.items():
        bass_lines = bls_by_prog.get(candidate_id, [])

        if not plans or not bass_lines:
            continue

        # Cross-product: one ArrangementCandidate per (voicing_plan, bass_line) pair
        family_candidates = []
        for vp in plans:
            for bl in bass_lines:
                ac = assembler.assemble_one(
                    progression_candidate_id=candidate_id,
                    session_id=session_id,
                    voicing_plan=vp,
                    bass_line=bl,
                    intent_tags=intent_tags,
                    rationale=f"{vp.metadata.get('voicing_type', 'voicing')} + {bl.style_mode} bass",
                )
                family_candidates.append(ac)

        now = utc_now()
        family = ArrangementFamily(
            id=f"fam_{ULID()}",
            type="arrangement_family",
            status="active",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            root_arrangement_candidate_id=family_candidates[0].id,
            member_arrangement_candidate_ids=[c.id for c in family_candidates],
        )
        all_families.append(family.model_dump(mode="json"))
        all_candidates.extend(c.model_dump(mode="json") for c in family_candidates)

    return {
        "arrangement_candidates": all_candidates,
        "arrangement_families": all_families,
    }
