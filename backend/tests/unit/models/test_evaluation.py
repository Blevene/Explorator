"""Tests for evaluation, scoring, and objective weight models."""

import pytest
from pydantic import ValidationError

from explorator.models.evaluation import (
    AggregateScorecard,
    EvaluationBundle,
    GrooveEvaluation,
    MelodyHarmonyEvaluation,
    ObjectiveWeights,
    PlayabilityEvaluation,
    RegisterDensityEvaluation,
    TheoryEvaluation,
    VoiceLeadingEvaluation,
)

# ---------------------------------------------------------------------------
# TheoryEvaluation
# ---------------------------------------------------------------------------


def test_theory_evaluation_defaults() -> None:
    ev = TheoryEvaluation(
        id="te_01",
        type="theory_evaluation",
        status="completed",
        candidate_id="prog_01",
        evaluation_type="theory",
    )
    assert ev.genre_fit == 0.0
    assert ev.emotional_fit == 0.0
    assert ev.theoretical_coherence == 0.0
    assert ev.cadence_quality == 0.0
    assert ev.novelty == 0.0
    assert ev.loopability == 0.0
    assert ev.notes == []


def test_theory_evaluation_custom_scores() -> None:
    ev = TheoryEvaluation(
        id="te_02",
        type="theory_evaluation",
        status="completed",
        candidate_id="prog_01",
        evaluation_type="theory",
        genre_fit=0.9,
        novelty=0.7,
    )
    assert ev.genre_fit == 0.9
    assert ev.novelty == 0.7


def test_theory_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        TheoryEvaluation(
            id="te_03",
            type="theory_evaluation",
            status="completed",
            evaluation_type="theory",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# VoiceLeadingEvaluation
# ---------------------------------------------------------------------------


def test_voice_leading_evaluation_defaults() -> None:
    ev = VoiceLeadingEvaluation(
        id="vle_01",
        type="voice_leading_evaluation",
        status="completed",
        candidate_id="prog_01",
        evaluation_type="voice_leading",
    )
    assert ev.smoothness_score == 0.0
    assert ev.common_tone_retention_score == 0.0
    assert ev.awkward_leap_penalty == 0.0
    assert ev.resolution_quality == 0.0


def test_voice_leading_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        VoiceLeadingEvaluation(
            id="vle_02",
            type="voice_leading_evaluation",
            status="completed",
            evaluation_type="voice_leading",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# RegisterDensityEvaluation
# ---------------------------------------------------------------------------


def test_register_density_evaluation_defaults() -> None:
    ev = RegisterDensityEvaluation(
        id="rde_01",
        type="register_density_evaluation",
        status="completed",
        candidate_id="arr_01",
        evaluation_type="register_density",
    )
    assert ev.register_balance_score == 0.0
    assert ev.mud_risk_score == 0.0
    assert ev.overcrowding_risk_score == 0.0
    assert ev.spacing_quality == 0.0


def test_register_density_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        RegisterDensityEvaluation(
            id="rde_02",
            type="register_density_evaluation",
            status="completed",
            evaluation_type="register_density",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# PlayabilityEvaluation
# ---------------------------------------------------------------------------


def test_playability_evaluation_defaults() -> None:
    ev = PlayabilityEvaluation(
        id="pe_01",
        type="playability_evaluation",
        status="completed",
        candidate_id="arr_01",
        evaluation_type="playability",
    )
    assert ev.piano_playability == 0.0
    assert ev.guitar_playability == 0.0
    assert ev.ensemble_playability == 0.0
    assert ev.simplification_recommendations == []


def test_playability_evaluation_with_recommendations() -> None:
    ev = PlayabilityEvaluation(
        id="pe_02",
        type="playability_evaluation",
        status="completed",
        candidate_id="arr_01",
        evaluation_type="playability",
        piano_playability=0.8,
        simplification_recommendations=["Drop inner voice on beat 3"],
    )
    assert ev.piano_playability == 0.8
    assert len(ev.simplification_recommendations) == 1


def test_playability_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        PlayabilityEvaluation(
            id="pe_03",
            type="playability_evaluation",
            status="completed",
            evaluation_type="playability",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# GrooveEvaluation
# ---------------------------------------------------------------------------


def test_groove_evaluation_defaults() -> None:
    ev = GrooveEvaluation(
        id="ge_01",
        type="groove_evaluation",
        status="completed",
        candidate_id="arr_01",
        evaluation_type="groove",
    )
    assert ev.groove_authenticity == 0.0
    assert ev.rhythmic_coherence == 0.0
    assert ev.style_alignment == 0.0


def test_groove_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        GrooveEvaluation(
            id="ge_02",
            type="groove_evaluation",
            status="completed",
            evaluation_type="groove",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MelodyHarmonyEvaluation
# ---------------------------------------------------------------------------


def test_melody_harmony_evaluation_defaults() -> None:
    ev = MelodyHarmonyEvaluation(
        id="mhe_01",
        type="melody_harmony_evaluation",
        status="completed",
        candidate_id="arr_01",
        evaluation_type="melody_harmony",
    )
    assert ev.melody_support_score == 0.0
    assert ev.tension_justification_score == 0.0
    assert ev.collision_risk_score == 0.0


def test_melody_harmony_evaluation_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        MelodyHarmonyEvaluation(
            id="mhe_02",
            type="melody_harmony_evaluation",
            status="completed",
            evaluation_type="melody_harmony",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# EvaluationBundle
# ---------------------------------------------------------------------------


def test_evaluation_bundle_minimal() -> None:
    bundle = EvaluationBundle(
        id="eb_01",
        type="evaluation_bundle",
        status="active",
        candidate_id="prog_01",
        candidate_type="progression_candidate",
    )
    assert bundle.candidate_id == "prog_01"
    assert bundle.candidate_type == "progression_candidate"
    assert bundle.theory_evaluation_id is None
    assert bundle.voice_leading_evaluation_id is None
    assert bundle.register_density_evaluation_id is None
    assert bundle.playability_evaluation_id is None
    assert bundle.groove_evaluation_id is None
    assert bundle.melody_harmony_evaluation_id is None
    assert bundle.aggregate_scorecard_id is None


def test_evaluation_bundle_with_ids() -> None:
    bundle = EvaluationBundle(
        id="eb_02",
        type="evaluation_bundle",
        status="active",
        candidate_id="arr_01",
        candidate_type="arrangement_candidate",
        theory_evaluation_id="te_01",
        voice_leading_evaluation_id="vle_01",
        aggregate_scorecard_id="sc_01",
    )
    assert bundle.theory_evaluation_id == "te_01"
    assert bundle.aggregate_scorecard_id == "sc_01"


def test_evaluation_bundle_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        EvaluationBundle(
            id="eb_03",
            type="evaluation_bundle",
            status="active",
            candidate_type="progression_candidate",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# AggregateScorecard
# ---------------------------------------------------------------------------


def test_aggregate_scorecard_defaults() -> None:
    sc = AggregateScorecard(
        id="sc_01",
        type="aggregate_scorecard",
        status="completed",
        candidate_id="prog_01",
    )
    assert sc.scores == {}
    assert sc.weighted_total == 0.0
    assert sc.rank_within_round == 0
    assert sc.pareto_tags == []


def test_aggregate_scorecard_with_data() -> None:
    sc = AggregateScorecard(
        id="sc_02",
        type="aggregate_scorecard",
        status="completed",
        candidate_id="prog_01",
        scores={"theory": 0.85, "voice_leading": 0.70},
        weighted_total=0.78,
        rank_within_round=2,
        pareto_tags=["best_theory"],
    )
    assert sc.scores["theory"] == 0.85
    assert sc.weighted_total == 0.78
    assert sc.rank_within_round == 2
    assert "best_theory" in sc.pareto_tags


def test_aggregate_scorecard_requires_candidate_id() -> None:
    with pytest.raises(ValidationError):
        AggregateScorecard(
            id="sc_03",
            type="aggregate_scorecard",
            status="completed",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ObjectiveWeights
# ---------------------------------------------------------------------------


def test_objective_weights_defaults() -> None:
    ow = ObjectiveWeights(
        id="ow_01",
        type="objective_weights",
        status="active",
    )
    assert ow.profile_name == "default"
    assert ow.weights == {}


def test_objective_weights_valid_sum() -> None:
    ow = ObjectiveWeights(
        id="ow_02",
        type="objective_weights",
        status="active",
        weights={"theory": 0.4, "voice_leading": 0.3, "playability": 0.3},
    )
    assert abs(sum(ow.weights.values()) - 1.0) <= 0.01


def test_objective_weights_invalid_sum_raises_value_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ObjectiveWeights(
            id="ow_03",
            type="objective_weights",
            status="active",
            weights={"theory": 0.5, "voice_leading": 0.3},
        )
    assert "1.0" in str(exc_info.value) or "sum" in str(exc_info.value).lower()


def test_objective_weights_empty_dict_allowed() -> None:
    """Empty weights dict is valid (no constraint applies)."""
    ow = ObjectiveWeights(
        id="ow_04",
        type="objective_weights",
        status="active",
        weights={},
    )
    assert ow.weights == {}
