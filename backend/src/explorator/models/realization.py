"""Realization models: voicings, bass, arrangements."""

from typing import Literal

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity, CandidateBase

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

VoicingType = Literal["open", "close", "drop2", "drop3"]
RegisterLabel = Literal["low", "mid", "mid_high", "high"]
DensityLevel = Literal["thin", "medium", "full"]


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class VoicingEvent(BaseModel):
    """A single voiced chord event in a voicing plan."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 4.0
    pitches: list[str]
    chord_symbol: str


class BassNoteEvent(BaseModel):
    """A single bass note event in a bass line."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 1.0
    pitch: str
    velocity: int = 80


# ---------------------------------------------------------------------------
# Voice leading
# ---------------------------------------------------------------------------


class VoiceLeadingCheck(BaseModel):
    """Metrics for evaluating voice leading quality between two chords."""

    common_tones: int
    total_semitone_distance: int
    max_leap: int
    has_parallel_fifths: bool
    has_parallel_octaves: bool


# ---------------------------------------------------------------------------
# Preference models
# ---------------------------------------------------------------------------


class VoicingPreferences(BaseModel):
    """Genre-level voicing style preferences."""

    default_voicing_type: VoicingType = "open"
    default_register: RegisterLabel = "mid"
    default_density: DensityLevel = "medium"
    default_voice_count: int = 4
    favor_extensions: bool = False
    top_voice_continuity: str = "medium"
    variant_voicing_types: list[VoicingType] = Field(
        default_factory=lambda: ["open", "drop2", "close"]
    )


class BassPreferences(BaseModel):
    """Genre-level bass style preferences."""

    default_bass_mode: str = "supportive"
    default_register: str = "low"
    rhythmic_density: str = "moderate"


# ---------------------------------------------------------------------------
# LLM instruction / response models
# ---------------------------------------------------------------------------


class ChordVoicingInstruction(BaseModel):
    """Detailed voicing specification for a single chord."""

    chord_symbol: str
    bar: int
    voicing_type: VoicingType
    register: RegisterLabel
    density: DensityLevel
    pitches: list[str]
    voice_leading_check: VoiceLeadingCheck | None = None


class VoicingStrategyResponse(BaseModel):
    """Full voicing strategy returned by the LLM for a progression."""

    global_strategy: str
    density_level: str
    register_profile: str
    voicing_instructions: list[ChordVoicingInstruction]
    rationale: str = ""


class VariantConfig(BaseModel):
    """Configuration for a single arrangement variant."""

    label: str
    voicing_type: VoicingType | None = None
    density: DensityLevel | None = None
    register: RegisterLabel | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Domain entity models
# ---------------------------------------------------------------------------


class VoicingPlan(BaseEntity):
    """How a progression is voiced."""

    progression_candidate_id: str | None = None
    instrument: str = "electric_piano"
    global_strategy: str = ""
    density_level: str = "medium"
    register_profile: str = "mid_high"
    voicing_events: list[VoicingEvent] = Field(default_factory=list)


class BassLine(BaseEntity):
    """Bass realization layer."""

    progression_candidate_id: str | None = None
    style_mode: str = "supportive"
    contour_type: str = "mostly_stepwise"
    rhythmic_density: str = "low"
    relationship_to_harmony: str = "stabilizing"
    note_events: list[BassNoteEvent] = Field(default_factory=list)


class ArrangementCandidate(CandidateBase):
    """Realized musical object combining progression + realization layers."""

    progression_candidate_id: str
    voicing_plan_id: str | None = None
    bass_line_id: str | None = None
    melodic_complement_id: str | None = None
    groove_pattern_id: str | None = None
    instrument_realization_plan_id: str | None = None
    render_artifact_ids: list[str] = Field(default_factory=list)


class ArrangementFamily(BaseEntity):
    """Groups related arrangement variants."""

    session_id: str
    root_arrangement_candidate_id: str
    member_arrangement_candidate_ids: list[str] = Field(default_factory=list)
    family_description: str = ""
