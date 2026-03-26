"""Tests for harmony domain models."""

import pytest
from pydantic import ValidationError

from explorator.models.harmony import (
    ChordEvent,
    ProgressionCandidate,
    ProgressionFamily,
    RomanNumeralAnalysis,
)

# ---------------------------------------------------------------------------
# ChordEvent
# ---------------------------------------------------------------------------


def test_chord_event_minimal() -> None:
    event = ChordEvent(bar=1, symbol="Cmaj7")
    assert event.bar == 1
    assert event.symbol == "Cmaj7"
    assert event.beat == 1.0
    assert event.duration_beats == 4.0
    assert event.function_label is None
    assert event.harmonic_role_tags == []


def test_chord_event_full() -> None:
    event = ChordEvent(
        bar=2,
        beat=3.0,
        duration_beats=2.0,
        symbol="Dm7",
        function_label="ii",
        harmonic_role_tags=["subdominant", "prep"],
    )
    assert event.beat == 3.0
    assert event.duration_beats == 2.0
    assert event.function_label == "ii"
    assert "subdominant" in event.harmonic_role_tags


def test_chord_event_requires_bar() -> None:
    with pytest.raises(ValidationError):
        ChordEvent(symbol="G7")  # type: ignore[call-arg]


def test_chord_event_requires_symbol() -> None:
    with pytest.raises(ValidationError):
        ChordEvent(bar=1)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ProgressionCandidate
# ---------------------------------------------------------------------------


def test_progression_candidate_minimal() -> None:
    candidate = ProgressionCandidate(
        id="prog_01",
        type="progression_candidate",
        status="candidate",
        session_id="sess_01",
        rationale="Test progression",
        key_center="C",
    )
    assert candidate.key_center == "C"
    assert candidate.mode == "major"
    assert candidate.phrase_length_bars == 8
    assert candidate.chord_events == []
    assert candidate.roman_numeral_analysis_id is None
    assert candidate.generator_mode == "balanced"
    assert candidate.source_type == "generated"


def test_progression_candidate_with_chord_events() -> None:
    events = [
        ChordEvent(bar=1, symbol="Cmaj7"),
        ChordEvent(bar=2, symbol="Am7"),
    ]
    candidate = ProgressionCandidate(
        id="prog_02",
        type="progression_candidate",
        status="candidate",
        session_id="sess_01",
        rationale="Two-chord loop",
        key_center="C",
        chord_events=events,
    )
    assert len(candidate.chord_events) == 2
    assert candidate.chord_events[0].symbol == "Cmaj7"


def test_progression_candidate_requires_key_center() -> None:
    with pytest.raises(ValidationError):
        ProgressionCandidate(
            id="prog_03",
            type="progression_candidate",
            status="candidate",
            session_id="sess_01",
            rationale="Missing key",
        )  # type: ignore[call-arg]


def test_progression_candidate_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        ProgressionCandidate(
            id="prog_04",
            type="progression_candidate",
            status="candidate",
            rationale="Missing session",
            key_center="D",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ProgressionFamily
# ---------------------------------------------------------------------------


def test_progression_family_minimal() -> None:
    family = ProgressionFamily(
        id="fam_01",
        type="progression_family",
        status="active",
        session_id="sess_01",
        root_progression_candidate_id="prog_01",
    )
    assert family.session_id == "sess_01"
    assert family.root_progression_candidate_id == "prog_01"
    assert family.member_progression_candidate_ids == []
    assert family.family_description == ""


def test_progression_family_with_members() -> None:
    family = ProgressionFamily(
        id="fam_02",
        type="progression_family",
        status="active",
        session_id="sess_01",
        root_progression_candidate_id="prog_01",
        member_progression_candidate_ids=["prog_02", "prog_03"],
        family_description="Variants of the opening vamp",
    )
    assert len(family.member_progression_candidate_ids) == 2
    assert family.family_description == "Variants of the opening vamp"


def test_progression_family_requires_root_id() -> None:
    with pytest.raises(ValidationError):
        ProgressionFamily(
            id="fam_03",
            type="progression_family",
            status="active",
            session_id="sess_01",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# RomanNumeralAnalysis
# ---------------------------------------------------------------------------


def test_roman_numeral_analysis_minimal() -> None:
    analysis = RomanNumeralAnalysis(
        id="rna_01",
        type="roman_numeral_analysis",
        status="completed",
        progression_candidate_id="prog_01",
    )
    assert analysis.progression_candidate_id == "prog_01"
    assert analysis.analysis_events == []
    assert analysis.analysis_notes == []


def test_roman_numeral_analysis_with_events() -> None:
    events = [
        {"bar": 1, "roman_numeral": "I", "quality": "maj7"},
        {"bar": 2, "roman_numeral": "vi", "quality": "m7"},
    ]
    analysis = RomanNumeralAnalysis(
        id="rna_02",
        type="roman_numeral_analysis",
        status="completed",
        progression_candidate_id="prog_01",
        analysis_events=events,
        analysis_notes=["Stable tonic area"],
    )
    assert len(analysis.analysis_events) == 2
    assert analysis.analysis_notes == ["Stable tonic area"]


def test_roman_numeral_analysis_requires_progression_id() -> None:
    with pytest.raises(ValidationError):
        RomanNumeralAnalysis(
            id="rna_03",
            type="roman_numeral_analysis",
            status="completed",
        )  # type: ignore[call-arg]
