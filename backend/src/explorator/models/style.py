"""GenreProfile, GenreRule, AntiPattern, HarmonicGrammar models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class GenreProfile(BaseEntity):
    """Operational representation of genre knowledge."""

    genre: str
    display_name: str = ""
    subgenre: str | None = None
    harmonic_vocabulary: list[str] = Field(default_factory=list)
    harmonic_tendencies: dict[str, str] = Field(default_factory=dict)
    voicing_tendencies: dict[str, str] = Field(default_factory=dict)
    bass_tendencies: dict[str, str] = Field(default_factory=dict)
    groove_tendencies: dict[str, str] = Field(default_factory=dict)
    common_devices: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    experimentation_envelope: dict[str, float] = Field(default_factory=dict)


class GenreRule(BaseEntity):
    """Individual reusable rule with weight and applicability conditions."""

    genre: str
    rule_type: str
    name: str
    description: str
    weight: float = 0.5
    applicability: dict[str, Any] = Field(default_factory=dict)
    anti_rule: bool = False


class AntiPattern(BaseEntity):
    """Pattern that breaks genre identity."""

    genre: str
    scope: str
    name: str
    description: str
    severity: float = 0.5


class HarmonicGrammar(BaseEntity):
    """Genre's operational harmonic syntax."""

    genre_profile_id: str
    preferred_chord_qualities: list[str] = Field(default_factory=list)
    allowed_borrowed_chords: list[str] = Field(default_factory=list)
    cadence_archetypes: list[str] = Field(default_factory=list)
    harmonic_rhythm_defaults: dict[str, float] = Field(default_factory=dict)
    functional_motion_bias: dict[str, float] = Field(default_factory=dict)
