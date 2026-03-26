"""Realization models: voicings, bass, arrangements."""

from pydantic import Field

from explorator.models.base import BaseEntity, CandidateBase


class VoicingPlan(BaseEntity):
    """How a progression is voiced."""

    progression_candidate_id: str | None = None
    instrument: str = "electric_piano"
    global_strategy: str = ""
    density_level: str = "medium"
    register_profile: str = "mid_high"
    voicing_events_json: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]


class BassLine(BaseEntity):
    """Bass realization layer."""

    progression_candidate_id: str | None = None
    style_mode: str = "supportive"
    contour_type: str = "mostly_stepwise"
    rhythmic_density: str = "low"
    relationship_to_harmony: str = "stabilizing"
    note_events_json: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]


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
