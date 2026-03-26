"""Evaluation, scoring, and objective weight models."""

from pydantic import Field, field_validator

from explorator.models.base import BaseEntity, EvaluationBase


class TheoryEvaluation(EvaluationBase):
    """Harmonic theory scoring."""

    genre_fit: float = 0.0
    emotional_fit: float = 0.0
    theoretical_coherence: float = 0.0
    cadence_quality: float = 0.0
    novelty: float = 0.0
    loopability: float = 0.0


class VoiceLeadingEvaluation(EvaluationBase):
    """Voice leading quality scoring."""

    smoothness_score: float = 0.0
    common_tone_retention_score: float = 0.0
    awkward_leap_penalty: float = 0.0
    resolution_quality: float = 0.0


class RegisterDensityEvaluation(EvaluationBase):
    """Register and density balance scoring."""

    register_balance_score: float = 0.0
    mud_risk_score: float = 0.0
    overcrowding_risk_score: float = 0.0
    spacing_quality: float = 0.0


class PlayabilityEvaluation(EvaluationBase):
    """Playability scoring per instrument."""

    piano_playability: float = 0.0
    guitar_playability: float = 0.0
    ensemble_playability: float = 0.0
    simplification_recommendations: list[str] = Field(default_factory=list)


class GrooveEvaluation(EvaluationBase):
    """Groove authenticity scoring. Deferred to M5."""

    groove_authenticity: float = 0.0
    rhythmic_coherence: float = 0.0
    style_alignment: float = 0.0


class MelodyHarmonyEvaluation(EvaluationBase):
    """Melody-harmony compatibility. Deferred to v1.5."""

    melody_support_score: float = 0.0
    tension_justification_score: float = 0.0
    collision_risk_score: float = 0.0


class EvaluationBundle(BaseEntity):
    """Groups all evaluations for one candidate."""

    candidate_id: str
    candidate_type: str
    theory_evaluation_id: str | None = None
    voice_leading_evaluation_id: str | None = None
    register_density_evaluation_id: str | None = None
    playability_evaluation_id: str | None = None
    groove_evaluation_id: str | None = None
    melody_harmony_evaluation_id: str | None = None
    aggregate_scorecard_id: str | None = None


class AggregateScorecard(BaseEntity):
    """Normalized final scores."""

    candidate_id: str
    scores: dict[str, float] = Field(default_factory=dict)
    weighted_total: float = 0.0
    rank_within_round: int = 0
    pareto_tags: list[str] = Field(default_factory=list)


class ObjectiveWeights(BaseEntity):
    """Configurable scoring weights per dimension."""

    profile_name: str = "default"
    weights: dict[str, float] = Field(default_factory=dict)

    @field_validator("weights")
    @classmethod
    def validate_weights_sum(cls, v: dict[str, float]) -> dict[str, float]:
        """Weights must sum to approximately 1.0 when non-empty."""
        if v and abs(sum(v.values()) - 1.0) > 0.01:
            msg = f"Weights must sum to ~1.0, got {sum(v.values()):.3f}"
            raise ValueError(msg)
        return v
