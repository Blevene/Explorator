from explorator.domain.realization.assembly import ArrangementAssembler
from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    BassNoteEvent,
    VoicingEvent,
    VoicingPlan,
)


def _make_voicing_plan(vp_id: str) -> VoicingPlan:
    return VoicingPlan(
        id=vp_id, type="voicing_plan", status="draft",
        voicing_events=[VoicingEvent(bar=1, pitches=["C4", "E4", "G4"], chord_symbol="C")],
    )


def _make_bass_line() -> BassLine:
    return BassLine(
        id="bl_01", type="bass_line", status="draft",
        note_events=[BassNoteEvent(bar=1, pitch="C2")],
    )


class TestArrangementAssembler:
    def test_assemble_single(self):
        assembler = ArrangementAssembler()
        ac = assembler.assemble_one(
            progression_candidate_id="prog_01", session_id="sess_01",
            voicing_plan=_make_voicing_plan("vp_01"), bass_line=_make_bass_line(),
            intent_tags=["dreamy"], rationale="open voicing, mid-high register",
        )
        assert isinstance(ac, ArrangementCandidate)
        assert ac.progression_candidate_id == "prog_01"
        assert ac.voicing_plan_id == "vp_01"
        assert ac.bass_line_id == "bl_01"
        assert ac.session_id == "sess_01"
        assert ac.type == "arrangement_candidate"
        assert ac.status == "draft"

    def test_assemble_family(self):
        assembler = ArrangementAssembler()
        plans = [_make_voicing_plan(f"vp_{i}") for i in range(3)]
        family, candidates = assembler.assemble_family(
            progression_candidate_id="prog_01", session_id="sess_01",
            voicing_plans=plans, bass_line=_make_bass_line(), intent_tags=["dreamy"],
        )
        assert isinstance(family, ArrangementFamily)
        assert len(candidates) == 3
        assert family.root_arrangement_candidate_id == candidates[0].id
        assert len(family.member_arrangement_candidate_ids) == 3
        for ac in candidates:
            assert ac.id in family.member_arrangement_candidate_ids
