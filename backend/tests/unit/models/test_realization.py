"""Tests for realization domain models."""

import pytest
from pydantic import ValidationError

from explorator.models.realization import (
    ArrangementCandidate,
    ArrangementFamily,
    BassLine,
    BassNoteEvent,
    BassPreferences,
    ChordVoicingInstruction,
    VariantConfig,
    VoiceLeadingCheck,
    VoicingEvent,
    VoicingPlan,
    VoicingPreferences,
    VoicingStrategyResponse,
)

# ---------------------------------------------------------------------------
# VoicingEvent
# ---------------------------------------------------------------------------


def test_voicing_event_minimal() -> None:
    evt = VoicingEvent(bar=1, pitches=["C4", "E4", "G4"], chord_symbol="C")
    assert evt.bar == 1
    assert evt.beat == 1.0
    assert evt.duration_beats == 4.0
    assert evt.pitches == ["C4", "E4", "G4"]
    assert evt.chord_symbol == "C"


def test_voicing_event_full() -> None:
    evt = VoicingEvent(
        bar=3,
        beat=2.5,
        duration_beats=2.0,
        pitches=["F3", "A3", "C4", "E4"],
        chord_symbol="Fmaj7",
    )
    assert evt.bar == 3
    assert evt.beat == 2.5
    assert evt.duration_beats == 2.0
    assert len(evt.pitches) == 4
    assert evt.chord_symbol == "Fmaj7"


def test_voicing_event_requires_bar_pitches_chord() -> None:
    with pytest.raises(ValidationError):
        VoicingEvent(pitches=["C4"], chord_symbol="C")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        VoicingEvent(bar=1, chord_symbol="C")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        VoicingEvent(bar=1, pitches=["C4"])  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# BassNoteEvent
# ---------------------------------------------------------------------------


def test_bass_note_event_minimal() -> None:
    evt = BassNoteEvent(bar=1, pitch="C2")
    assert evt.bar == 1
    assert evt.beat == 1.0
    assert evt.duration_beats == 1.0
    assert evt.pitch == "C2"
    assert evt.velocity == 80


def test_bass_note_event_full() -> None:
    evt = BassNoteEvent(
        bar=2,
        beat=3.0,
        duration_beats=0.5,
        pitch="G2",
        velocity=95,
    )
    assert evt.bar == 2
    assert evt.beat == 3.0
    assert evt.duration_beats == 0.5
    assert evt.pitch == "G2"
    assert evt.velocity == 95


def test_bass_note_event_requires_bar_and_pitch() -> None:
    with pytest.raises(ValidationError):
        BassNoteEvent(pitch="C2")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        BassNoteEvent(bar=1)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# VoiceLeadingCheck
# ---------------------------------------------------------------------------


def test_voice_leading_check_defaults() -> None:
    check = VoiceLeadingCheck(
        common_tones=2,
        total_semitone_distance=4,
        max_leap=5,
        has_parallel_fifths=False,
        has_parallel_octaves=False,
    )
    assert check.common_tones == 2
    assert check.total_semitone_distance == 4
    assert check.max_leap == 5
    assert check.has_parallel_fifths is False
    assert check.has_parallel_octaves is False


def test_voice_leading_check_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        VoiceLeadingCheck(  # type: ignore[call-arg]
            total_semitone_distance=4,
            max_leap=5,
            has_parallel_fifths=False,
            has_parallel_octaves=False,
        )


# ---------------------------------------------------------------------------
# VoicingPreferences
# ---------------------------------------------------------------------------


def test_voicing_preferences_defaults() -> None:
    prefs = VoicingPreferences()
    assert prefs.default_voicing_type == "open"
    assert prefs.default_register == "mid"
    assert prefs.default_density == "medium"
    assert prefs.default_voice_count == 4
    assert prefs.favor_extensions is False
    assert prefs.top_voice_continuity == "medium"
    assert prefs.variant_voicing_types == ["open", "drop2", "close"]


def test_voicing_preferences_custom() -> None:
    prefs = VoicingPreferences(
        default_voicing_type="drop2",
        default_register="high",
        default_density="thin",
        default_voice_count=3,
        favor_extensions=True,
        top_voice_continuity="high",
        variant_voicing_types=["drop2", "drop3"],
    )
    assert prefs.default_voicing_type == "drop2"
    assert prefs.default_register == "high"
    assert prefs.default_density == "thin"
    assert prefs.default_voice_count == 3
    assert prefs.favor_extensions is True
    assert prefs.top_voice_continuity == "high"
    assert prefs.variant_voicing_types == ["drop2", "drop3"]


def test_voicing_preferences_invalid_literal() -> None:
    with pytest.raises(ValidationError):
        VoicingPreferences(default_voicing_type="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        VoicingPreferences(default_register="ultra_high")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        VoicingPreferences(default_density="sparse")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BassPreferences
# ---------------------------------------------------------------------------


def test_bass_preferences_defaults() -> None:
    prefs = BassPreferences()
    assert prefs.default_bass_mode == "supportive"
    assert prefs.default_register == "low"
    assert prefs.rhythmic_density == "moderate"


def test_bass_preferences_custom() -> None:
    prefs = BassPreferences(
        default_bass_mode="walking",
        default_register="mid",
        rhythmic_density="dense",
    )
    assert prefs.default_bass_mode == "walking"
    assert prefs.default_register == "mid"
    assert prefs.rhythmic_density == "dense"


# ---------------------------------------------------------------------------
# ChordVoicingInstruction
# ---------------------------------------------------------------------------


def test_chord_voicing_instruction_minimal() -> None:
    instr = ChordVoicingInstruction(
        chord_symbol="Cmaj7",
        bar=1,
        voicing_type="open",
        density="medium",
        pitches=["C3", "E4", "G4", "B4"],
    )
    assert instr.chord_symbol == "Cmaj7"
    assert instr.bar == 1
    assert instr.voicing_type == "open"
    assert instr.density == "medium"
    assert len(instr.pitches) == 4
    assert instr.voice_leading_check is None


def test_chord_voicing_instruction_with_vl_check() -> None:
    vl = VoiceLeadingCheck(
        common_tones=1,
        total_semitone_distance=3,
        max_leap=4,
        has_parallel_fifths=False,
        has_parallel_octaves=False,
    )
    instr = ChordVoicingInstruction(
        chord_symbol="G7",
        bar=4,
        voicing_type="drop2",
        density="full",
        pitches=["G2", "B3", "D4", "F4"],
        voice_leading_check=vl,
    )
    assert instr.voice_leading_check is not None
    assert instr.voice_leading_check.common_tones == 1


# ---------------------------------------------------------------------------
# VoicingStrategyResponse
# ---------------------------------------------------------------------------


def test_voicing_strategy_response_minimal() -> None:
    instr = ChordVoicingInstruction(
        chord_symbol="Am7",
        bar=2,
        voicing_type="close",
        density="medium",
        pitches=["A3", "C4", "E4", "G4"],
    )
    resp = VoicingStrategyResponse(
        global_strategy="mid-register close voicings",
        density_level="medium",
        register_profile="mid",
        per_chord=[instr],
    )
    assert resp.global_strategy == "mid-register close voicings"
    assert resp.density_level == "medium"
    assert len(resp.per_chord) == 1
    assert resp.rationale == ""


def test_voicing_strategy_response_with_rationale() -> None:
    resp = VoicingStrategyResponse(
        global_strategy="open voicings",
        density_level="thin",
        register_profile="high",
        rationale="Sparse for melody room",
    )
    assert resp.rationale == "Sparse for melody room"


# ---------------------------------------------------------------------------
# VariantConfig
# ---------------------------------------------------------------------------


def test_variant_config_minimal() -> None:
    cfg = VariantConfig(label="dense")
    assert cfg.label == "dense"
    assert cfg.voicing_type is None
    assert cfg.density is None
    assert cfg.description == ""


def test_variant_config_full() -> None:
    cfg = VariantConfig(
        label="sparse_high",
        voicing_type="drop3",
        density="thin",
        description="High register sparse variant",
    )
    assert cfg.label == "sparse_high"
    assert cfg.voicing_type == "drop3"
    assert cfg.density == "thin"
    assert cfg.description == "High register sparse variant"


def test_variant_config_invalid_literal() -> None:
    with pytest.raises(ValidationError):
        VariantConfig(label="x", voicing_type="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        VariantConfig(label="x", density="ultra_dense")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# VoicingPlan — now uses list[VoicingEvent]
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
    events = [
        VoicingEvent(bar=1, pitches=["C3", "E4", "G4", "B4"], chord_symbol="Cmaj7"),
        VoicingEvent(bar=2, pitches=["A2", "C4", "E4", "G4"], chord_symbol="Am7"),
    ]
    plan = VoicingPlan(
        id="vp_03",
        type="voicing_plan",
        status="active",
        voicing_events=events,
    )
    assert len(plan.voicing_events) == 2
    assert plan.voicing_events[0].chord_symbol == "Cmaj7"
    assert plan.voicing_events[1].bar == 2


def test_voicing_plan_rejects_raw_dicts() -> None:
    """Raw dict events should fail validation since we now require VoicingEvent."""
    with pytest.raises(ValidationError):
        VoicingPlan(
            id="vp_04",
            type="voicing_plan",
            status="active",
            voicing_events=[{"bar": 1, "notes": [60, 64, 67, 71]}],
        )


def test_voicing_plan_requires_id() -> None:
    with pytest.raises(ValidationError):
        VoicingPlan(type="voicing_plan", status="active")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# BassLine — now uses list[BassNoteEvent]
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
        note_events=[BassNoteEvent(bar=1, beat=1.0, pitch="C2")],
    )
    assert bass.style_mode == "walking"
    assert bass.rhythmic_density == "high"
    assert len(bass.note_events) == 1
    assert bass.note_events[0].pitch == "C2"


def test_bass_line_rejects_raw_dicts() -> None:
    """Raw dict events should fail since we now require BassNoteEvent."""
    with pytest.raises(ValidationError):
        BassLine(
            id="bl_03",
            type="bass_line",
            status="active",
            note_events=[{"bar": 1, "beat": 1.0, "pitch": 36}],
        )


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


# ---------------------------------------------------------------------------
# BassPreferences — variant_bass_modes
# ---------------------------------------------------------------------------


class TestBassPreferencesVariantModes:
    def test_default_variant_bass_modes(self):
        bp = BassPreferences()
        assert bp.variant_bass_modes == ["supportive"]

    def test_custom_variant_bass_modes(self):
        bp = BassPreferences(variant_bass_modes=["supportive", "pedal"])
        assert len(bp.variant_bass_modes) == 2
