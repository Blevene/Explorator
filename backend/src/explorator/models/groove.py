"""Groove models: rhythmic events, patterns, and preferences."""

from pydantic import BaseModel, Field

from explorator.models.base import BaseEntity

# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


class GrooveEvent(BaseModel):
    """A single rhythmic event in a groove pattern."""

    beat: float
    duration_beats: float
    velocity: int
    accent: bool = False


# ---------------------------------------------------------------------------
# Domain entity models
# ---------------------------------------------------------------------------


class GroovePattern(BaseEntity):
    """Rhythmic template entity for a session arrangement."""

    session_id: str
    arrangement_candidate_id: str | None = None
    genre: str
    time_signature: str = "4/4"
    swing_amount: float = 0.0
    density: float = 0.5
    pattern_events: list[GrooveEvent] = Field(default_factory=list)
    source_template: str = "straight_eighths"
    variation_seed: int | None = None


# ---------------------------------------------------------------------------
# Preference models
# ---------------------------------------------------------------------------


class GroovePreferences(BaseModel):
    """Genre-level groove style preferences, parsed from genre YAML groove_tendencies."""

    comp_density: str = "medium"
    articulation_style: str = "straight"
    syncopation_level: str = "light"

    @classmethod
    def from_genre_tendencies(cls, tendencies: dict[str, str]) -> "GroovePreferences":
        """Build a GroovePreferences from a genre's groove_tendencies dict.

        Unknown keys are silently ignored; missing keys fall back to defaults.
        """
        known_fields = {"comp_density", "articulation_style", "syncopation_level"}
        filtered = {k: v for k, v in tendencies.items() if k in known_fields}
        return cls(**filtered)
