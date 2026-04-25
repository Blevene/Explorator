"""Combines voicing plans + bass lines into arrangement candidates."""

from ulid import ULID

from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    VoicingPlan,
)
from explorator.utils import utc_now


class ArrangementAssembler:
    def assemble_one(
        self,
        progression_candidate_id: str,
        session_id: str,
        voicing_plan: VoicingPlan,
        bass_line: BassLine,
        intent_tags: list[str],
        rationale: str,
    ) -> ArrangementCandidate:
        now = utc_now()
        return ArrangementCandidate(
            id=f"arr_{ULID()}",
            type="arrangement_candidate",
            status="draft",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            progression_candidate_id=progression_candidate_id,
            voicing_plan_id=voicing_plan.id,
            bass_line_id=bass_line.id,
            intent_tags=intent_tags,
            rationale=rationale,
        )

    def assemble_family(
        self,
        progression_candidate_id: str,
        session_id: str,
        voicing_plans: list[VoicingPlan],
        bass_line: BassLine,
        intent_tags: list[str],
    ) -> tuple[ArrangementFamily, list[ArrangementCandidate]]:
        candidates = [
            self.assemble_one(
                progression_candidate_id=progression_candidate_id,
                session_id=session_id,
                voicing_plan=vp,
                bass_line=bass_line,
                intent_tags=intent_tags,
                rationale=f"{vp.global_strategy} ({vp.register_profile} register)",
            )
            for vp in voicing_plans
        ]
        now = utc_now()
        family = ArrangementFamily(
            id=f"fam_{ULID()}",
            type="arrangement_family",
            status="active",
            created_at=now,
            updated_at=now,
            session_id=session_id,
            root_arrangement_candidate_id=candidates[0].id,
            member_arrangement_candidate_ids=[c.id for c in candidates],
        )
        return family, candidates
