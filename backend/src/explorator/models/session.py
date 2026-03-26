"""Session, SessionContext, and CreativeBrief models."""

from pydantic import Field

from explorator.models.base import BaseEntity


class Session(BaseEntity):
    """Top-level container for one exploration run."""

    mode: str = "full_exploration"
    creative_brief_id: str | None = None
    genre_profile_id: str | None = None
    search_plan_id: str | None = None
    progression_candidate_ids: list[str] = Field(default_factory=list)
    arrangement_candidate_ids: list[str] = Field(default_factory=list)
    feedback_event_ids: list[str] = Field(default_factory=list)
    final_selection_id: str | None = None
    provenance_trace_id: str | None = None


class CreativeBrief(BaseEntity):
    """Normalized statement of user intent."""

    genre: str
    subgenre: str | None = None
    mood_targets: list[str] = Field(default_factory=list)
    energy_level: str | None = None
    key_center: str | None = None
    mode: str | None = "major"
    meter: str = "4/4"
    tempo_hint_bpm: int | None = None
    phrase_length_bars: int = 8
    form_hint: str | None = None
    complexity_target: str = "medium"
    novelty_target: str = "moderate"
    generation_mode: str = "balanced"
    instrumentation_targets: list[str] = Field(default_factory=list)
    must_have_constraints: dict[str, bool] = Field(default_factory=dict)
    avoid_constraints: dict[str, bool] = Field(default_factory=dict)
    seed_progression: list[str] | None = None
    seed_melody_id: str | None = None
    seed_bassline_id: str | None = None
    reference_artists: list[str] = Field(default_factory=list)
    user_language_notes: list[str] = Field(default_factory=list)


class SessionContext(BaseEntity):
    """Dynamic in-session state."""

    session_id: str
    active_phase: str = "initialized"
    current_round: int = 0
    selected_progression_family_ids: list[str] = Field(default_factory=list)
    selected_arrangement_family_ids: list[str] = Field(default_factory=list)
    search_budget_remaining: int = 12
    current_objective_weights_id: str | None = None
