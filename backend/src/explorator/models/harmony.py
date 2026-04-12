"""Harmonic generation models."""

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity, CandidateBase


class ChordEvent(BaseModel):
    """One harmonic event in time (embedded, not a graph node)."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 4.0
    symbol: str
    function_label: str | None = None
    harmonic_role_tags: list[str] = Field(default_factory=list)


class ProgressionCandidate(CandidateBase):
    """Candidate chord progression before realization."""

    key_center: str
    mode: str = "major"
    phrase_length_bars: int = 8
    chord_events: list[ChordEvent] = Field(default_factory=list)
    chord_symbols: list[str] = Field(default_factory=list)
    roman_numerals: list[str] = Field(default_factory=list)
    roman_numeral_analysis_id: str | None = None
    generator_mode: str = "balanced"
    source_type: str = "generated"


class ProgressionFamily(BaseEntity):
    """Groups related harmonic variants."""

    session_id: str
    root_progression_candidate_id: str
    member_progression_candidate_ids: list[str] = Field(default_factory=list)
    family_description: str = ""


class RomanNumeralAnalysis(BaseEntity):
    """Symbolic harmonic interpretation."""

    progression_candidate_id: str
    analysis_events: list[dict[str, str | float]] = Field(default_factory=list)
    analysis_notes: list[str] = Field(default_factory=list)
