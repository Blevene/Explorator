"""Tests for realization domain models."""

import pytest
from pydantic import ValidationError

from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    VoicingPlan,
)

# ---------------------------------------------------------------------------
# VoicingPlan
# ---------------------------------------------------------------------------


def test_voicing_plan_minimal() -> None:
    plan = VoicingPlan(
        id="vp_01",
        type="voicing_plan",
        status="active",
    )
    assert plan.progression_candidate_id is None
    assert plan.instrument == "electric_piano"
    assert plan.global_strategy == ""
    assert plan.density_level == "medium"
    assert plan.register_profile == "mid_high"
    assert plan.voicing_events == []


def test_voicing_plan_with_progression() -> None:
    plan = VoicingPlan(
        id="vp_02",
        type="voicing_plan",
        status="active",
        progression_candidate_id="prog_01",
        instrument="acoustic_guitar",
        density_level="sparse",
        register_profile="high",
    )
    assert plan.progression_candidate_id == "prog_01"
    assert plan.instrument == "acoustic_guitar"
    assert plan.density_level == "sparse"


def test_voicing_plan_with_events() -> None:
    events = [{"bar": 1, "notes": [60, 64, 67, 71]}, {"bar": 2, "notes": [57, 60, 64, 67]}]
    plan = VoicingPlan(
        id="vp_03",
        type="voicing_plan",
        status="active",
        voicing_events=events,
    )
    assert len(plan.voicing_events) == 2


def test_voicing_plan_requires_id() -> None:
    with pytest.raises(ValidationError):
        VoicingPlan(type="voicing_plan", status="active")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# BassLine
# ---------------------------------------------------------------------------


def test_bass_line_minimal() -> None:
    bass = BassLine(
        id="bl_01",
        type="bass_line",
        status="active",
    )
    assert bass.progression_candidate_id is None
    assert bass.style_mode == "supportive"
    assert bass.contour_type == "mostly_stepwise"
    assert bass.rhythmic_density == "low"
    assert bass.relationship_to_harmony == "stabilizing"
    assert bass.note_events == []


def test_bass_line_full() -> None:
    bass = BassLine(
        id="bl_02",
        type="bass_line",
        status="active",
        progression_candidate_id="prog_01",
        style_mode="walking",
        contour_type="arpeggiated",
        rhythmic_density="high",
        relationship_to_harmony="complementing",
        note_events=[{"bar": 1, "beat": 1.0, "pitch": 36}],
    )
    assert bass.style_mode == "walking"
    assert bass.rhythmic_density == "high"
    assert len(bass.note_events) == 1


def test_bass_line_requires_id() -> None:
    with pytest.raises(ValidationError):
        BassLine(type="bass_line", status="active")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ArrangementCandidate
# ---------------------------------------------------------------------------


def test_arrangement_candidate_minimal() -> None:
    arr = ArrangementCandidate(
        id="arr_01",
        type="arrangement_candidate",
        status="candidate",
        session_id="sess_01",
        rationale="Basic realization",
        progression_candidate_id="prog_01",
    )
    assert arr.progression_candidate_id == "prog_01"
    assert arr.voicing_plan_id is None
    assert arr.bass_line_id is None
    assert arr.melodic_complement_id is None
    assert arr.groove_pattern_id is None
    assert arr.instrument_realization_plan_id is None
    assert arr.render_artifact_ids == []


def test_arrangement_candidate_with_layers() -> None:
    arr = ArrangementCandidate(
        id="arr_02",
        type="arrangement_candidate",
        status="candidate",
        session_id="sess_01",
        rationale="Full realization",
        progression_candidate_id="prog_01",
        voicing_plan_id="vp_01",
        bass_line_id="bl_01",
        render_artifact_ids=["ra_01", "ra_02"],
    )
    assert arr.voicing_plan_id == "vp_01"
    assert arr.bass_line_id == "bl_01"
    assert len(arr.render_artifact_ids) == 2


def test_arrangement_candidate_requires_progression_id() -> None:
    with pytest.raises(ValidationError):
        ArrangementCandidate(
            id="arr_03",
            type="arrangement_candidate",
            status="candidate",
            session_id="sess_01",
            rationale="Missing progression ref",
        )  # type: ignore[call-arg]


def test_arrangement_candidate_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ArrangementCandidate(
            id="arr_04",
            type="arrangement_candidate",
            status="candidate",
            rationale="Missing session",
            progression_candidate_id="prog_01",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ArrangementFamily
# ---------------------------------------------------------------------------


def test_arrangement_family_minimal() -> None:
    family = ArrangementFamily(
        id="afam_01",
        type="arrangement_family",
        status="active",
        session_id="sess_01",
        root_arrangement_candidate_id="arr_01",
    )
    assert family.root_arrangement_candidate_id == "arr_01"
    assert family.member_arrangement_candidate_ids == []
    assert family.family_description == ""


def test_arrangement_family_with_members() -> None:
    family = ArrangementFamily(
        id="afam_02",
        type="arrangement_family",
        status="active",
        session_id="sess_01",
        root_arrangement_candidate_id="arr_01",
        member_arrangement_candidate_ids=["arr_02", "arr_03"],
        family_description="Dense vs sparse variants",
    )
    assert len(family.member_arrangement_candidate_ids) == 2
    assert "Dense" in family.family_description


def test_arrangement_family_requires_root_id() -> None:
    with pytest.raises(ValidationError):
        ArrangementFamily(
            id="afam_03",
            type="arrangement_family",
            status="active",
            session_id="sess_01",
        )  # type: ignore[call-arg]
