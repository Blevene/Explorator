"""Melody models: note events, melodic complements, strategy responses, and preferences."""

from __future__ import annotations

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class MelodicNoteEvent(BaseModel):
    """A single note event in a melodic complement."""

    bar: int
    beat: float = 1.0
    duration_beats: float = 1.0
    pitch: str  # e.g. "C5"
    velocity: int = 80


# ---------------------------------------------------------------------------
# Strategy response models (Gemini structured output)
# ---------------------------------------------------------------------------


class PhraseInstruction(BaseModel):
    """Per-phrase melodic instructions from the LLM strategy."""

    start_bar: int
    end_bar: int  # inclusive
    contour: str  # arch | descending | ascending | wave | static
    density: str  # sparse | moderate | active
    strong_beat_targets: list[str] = Field(default_factory=list)
    rest_after: bool = False


class MelodicStrategyResponse(BaseModel):
    """LLM-generated melodic strategy for an arrangement."""

    range_low: str  # e.g. "C5"
    range_high: str  # e.g. "C6"
    overall_contour: str
    phrase_instructions: list[PhraseInstruction] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=200)


# ---------------------------------------------------------------------------
# Domain entity
# ---------------------------------------------------------------------------


class MelodicComplement(BaseEntity):
    """System-generated single-line melody for an arrangement."""

    arrangement_candidate_id: str
    groove_pattern_id: str | None = None
    note_events: list[MelodicNoteEvent] = Field(default_factory=list)
    range_low: str = ""
    range_high: str = ""
    contour_type: str = ""
    source_strategy: str = ""


# ---------------------------------------------------------------------------
# Preference models (parsed from genre YAML)
# ---------------------------------------------------------------------------


class MelodicPreferences(BaseModel):
    """Genre-derived melodic preferences."""

    motion_preference: str = "stepwise"  # stepwise | leaping | mixed
    range_placement: str = "above_voicing"
    density: str = "moderate"  # sparse | moderate | active
    phrase_length: int = 4  # 2 | 4
    strong_beat_preference: str = "chord_tones"
    rest_between_phrases: bool = True

    @classmethod
    def from_genre_tendencies(cls, tendencies: dict[str, str]) -> MelodicPreferences:
        """Build preferences from genre YAML melodic_tendencies section."""
        phrase_length_raw = tendencies.get("phrase_length", "4")
        try:
            phrase_length = int(phrase_length_raw)
        except (ValueError, TypeError):
            phrase_length = 4

        rest_raw = tendencies.get("rest_between_phrases", True)
        if isinstance(rest_raw, str):
            rest_between = rest_raw.lower() != "false"
        else:
            rest_between = bool(rest_raw)

        return cls(
            motion_preference=tendencies.get("motion_preference", "stepwise"),
            range_placement=tendencies.get("range_placement", "above_voicing"),
            density=tendencies.get("density", "moderate"),
            phrase_length=phrase_length,
            strong_beat_preference=tendencies.get("strong_beat_preference", "chord_tones"),
            rest_between_phrases=rest_between,
        )
