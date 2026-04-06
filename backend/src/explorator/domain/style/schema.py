"""Pydantic models for validating genre YAML files."""

from typing import Any

from pydantic import BaseModel, Field


class GenreProfileYAML(BaseModel):
    """Schema for genre profile YAML files."""

    genre: str
    display_name: str
    version: int = 1

    harmonic_vocabulary: list[str] = Field(default_factory=list)
    harmonic_tendencies: dict[str, str] = Field(default_factory=dict)
    voicing_tendencies: dict[str, str] = Field(default_factory=dict)
    bass_tendencies: dict[str, str] = Field(default_factory=dict)
    groove_tendencies: dict[str, str] = Field(default_factory=dict)
    common_devices: list[str] = Field(default_factory=list)
    experimentation_envelope: dict[str, float] = Field(default_factory=dict)
    voicing_preferences: dict[str, Any] = Field(default_factory=dict)
    bass_preferences: dict[str, Any] = Field(default_factory=dict)


class RuleEntryYAML(BaseModel):
    """One rule within a rules YAML file."""

    name: str
    type: str
    weight: float = 0.5
    description: str = ""
    applicability: dict[str, list[str]] = Field(default_factory=dict)


class AntiPatternEntryYAML(BaseModel):
    """One anti-pattern within a rules YAML file."""

    name: str
    scope: str
    severity: float = 0.5
    description: str = ""


class GenreRulesYAML(BaseModel):
    """Schema for genre rules YAML files."""

    rules: list[RuleEntryYAML] = Field(default_factory=list)
    anti_patterns: list[AntiPatternEntryYAML] = Field(default_factory=list)


class HarmonicGrammarYAML(BaseModel):
    """Schema for harmonic grammar YAML files."""

    genre_profile_id: str
    preferred_chord_qualities: list[str] = Field(default_factory=list)
    allowed_borrowed_chords: list[str] = Field(default_factory=list)
    cadence_archetypes: list[str] = Field(default_factory=list)
    harmonic_rhythm_defaults: dict[str, float] = Field(default_factory=dict)
    functional_motion_bias: dict[str, float] = Field(default_factory=dict)
