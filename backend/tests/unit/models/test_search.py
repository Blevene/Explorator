"""Tests for search plan, round, mutation, and selection models."""

import pytest
from pydantic import ValidationError

from explorator.models.search import (
    FinalSelection,
    MutationRecord,
    ParetoFrontSnapshot,
    SearchPlan,
    SearchRound,
    StopConditions,
)

# ---------------------------------------------------------------------------
# StopConditions (embedded model, not a BaseEntity)
# ---------------------------------------------------------------------------


def test_stop_conditions_defaults() -> None:
    sc = StopConditions()
    assert sc.target_score == 8.5
    assert sc.max_rounds == 4


def test_stop_conditions_custom() -> None:
    sc = StopConditions(target_score=9.0, max_rounds=6)
    assert sc.target_score == 9.0
    assert sc.max_rounds == 6


# ---------------------------------------------------------------------------
# SearchPlan
# ---------------------------------------------------------------------------


def test_search_plan_minimal() -> None:
    plan = SearchPlan(
        id="sp_01",
        type="search_plan",
        status="active",
        session_id="sess_01",
    )
    assert plan.session_id == "sess_01"
    assert plan.search_strategy == "beam_plus_mutation"
    assert plan.initial_generation_count == 12
    assert plan.progression_selection_count == 4
    assert plan.arrangement_selection_count == 4
    assert plan.max_rounds == 4
    assert plan.mutation_budget_per_round == 6
    assert plan.diversity_target == 0.65
    assert plan.random_seed is None
    assert isinstance(plan.stop_conditions, StopConditions)


def test_search_plan_custom_strategy() -> None:
    plan = SearchPlan(
        id="sp_02",
        type="search_plan",
        status="active",
        session_id="sess_01",
        search_strategy="pure_mutation",
        initial_generation_count=20,
        random_seed=42,
    )
    assert plan.search_strategy == "pure_mutation"
    assert plan.initial_generation_count == 20
    assert plan.random_seed == 42


def test_search_plan_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        SearchPlan(
            id="sp_03",
            type="search_plan",
            status="active",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SearchRound
# ---------------------------------------------------------------------------


def test_search_round_minimal() -> None:
    rnd = SearchRound(
        id="sr_01",
        type="search_round",
        status="active",
        session_id="sess_01",
        round_number=1,
    )
    assert rnd.round_number == 1
    assert rnd.input_candidate_ids == []
    assert rnd.generated_candidate_ids == []
    assert rnd.selected_candidate_ids == []
    assert rnd.eliminated_candidate_ids == []
    assert rnd.notes == []


def test_search_round_with_candidates() -> None:
    rnd = SearchRound(
        id="sr_02",
        type="search_round",
        status="completed",
        session_id="sess_01",
        round_number=2,
        input_candidate_ids=["prog_01", "prog_02"],
        generated_candidate_ids=["prog_03", "prog_04", "prog_05"],
        selected_candidate_ids=["prog_03", "prog_05"],
        eliminated_candidate_ids=["prog_04"],
        notes=["High diversity round"],
    )
    assert len(rnd.generated_candidate_ids) == 3
    assert len(rnd.selected_candidate_ids) == 2
    assert rnd.notes == ["High diversity round"]


def test_search_round_requires_round_number() -> None:
    with pytest.raises(ValidationError):
        SearchRound(
            id="sr_03",
            type="search_round",
            status="active",
            session_id="sess_01",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MutationRecord
# ---------------------------------------------------------------------------


def test_mutation_record_minimal() -> None:
    rec = MutationRecord(
        id="mr_01",
        type="mutation_record",
        status="completed",
        source_candidate_id="prog_01",
        source_candidate_type="progression_candidate",
        result_candidate_id="prog_02",
        result_candidate_type="progression_candidate",
        mutation_scope="harmonic",
    )
    assert rec.source_candidate_id == "prog_01"
    assert rec.result_candidate_id == "prog_02"
    assert rec.mutation_scope == "harmonic"
    assert rec.changes == []
    assert rec.reason == ""
    assert rec.predicted_effects == []
    assert rec.actual_score_delta == {}


def test_mutation_record_with_changes() -> None:
    from explorator.models.search import MutationChange

    changes = [
        MutationChange(field="chord_events[2].symbol", operation="replace", description="ii→IV"),
    ]
    rec = MutationRecord(
        id="mr_02",
        type="mutation_record",
        status="completed",
        source_candidate_id="prog_01",
        source_candidate_type="progression_candidate",
        result_candidate_id="prog_02",
        result_candidate_type="progression_candidate",
        mutation_scope="harmonic",
        changes=changes,
        reason="Increase brightness",
        predicted_effects=["Higher genre_fit"],
        actual_score_delta={"genre_fit": 0.12},
    )
    assert len(rec.changes) == 1
    assert rec.reason == "Increase brightness"
    assert rec.actual_score_delta["genre_fit"] == 0.12


def test_mutation_record_requires_source_id() -> None:
    with pytest.raises(ValidationError):
        MutationRecord(
            id="mr_03",
            type="mutation_record",
            status="completed",
            source_candidate_type="progression_candidate",
            result_candidate_id="prog_02",
            result_candidate_type="progression_candidate",
            mutation_scope="harmonic",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ParetoFrontSnapshot
# ---------------------------------------------------------------------------


def test_pareto_front_snapshot_minimal() -> None:
    snap = ParetoFrontSnapshot(
        id="pfs_01",
        type="pareto_front_snapshot",
        status="completed",
        session_id="sess_01",
        round_number=1,
    )
    assert snap.round_number == 1
    assert snap.candidate_ids == []
    assert snap.axes == []


def test_pareto_front_snapshot_with_data() -> None:
    snap = ParetoFrontSnapshot(
        id="pfs_02",
        type="pareto_front_snapshot",
        status="completed",
        session_id="sess_01",
        round_number=2,
        candidate_ids=["prog_03", "prog_07"],
        axes=["theory", "novelty"],
    )
    assert len(snap.candidate_ids) == 2
    assert "novelty" in snap.axes


def test_pareto_front_snapshot_requires_round_number() -> None:
    with pytest.raises(ValidationError):
        ParetoFrontSnapshot(
            id="pfs_03",
            type="pareto_front_snapshot",
            status="completed",
            session_id="sess_01",
        )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# FinalSelection
# ---------------------------------------------------------------------------


def test_final_selection_minimal() -> None:
    sel = FinalSelection(
        id="fs_01",
        type="final_selection",
        status="completed",
        session_id="sess_01",
    )
    assert sel.selected_candidate_ids == []
    assert sel.selection_roles == {}
    assert sel.selection_notes == []


def test_final_selection_with_data() -> None:
    sel = FinalSelection(
        id="fs_02",
        type="final_selection",
        status="completed",
        session_id="sess_01",
        selected_candidate_ids=["arr_01", "arr_02"],
        selection_roles={"arr_01": "primary", "arr_02": "variation"},
        selection_notes=["Both approved by user"],
    )
    assert len(sel.selected_candidate_ids) == 2
    assert sel.selection_roles["arr_01"] == "primary"
    assert sel.selection_notes == ["Both approved by user"]


def test_final_selection_requires_session_id() -> None:
    with pytest.raises(ValidationError):
        FinalSelection(
            id="fs_03",
            type="final_selection",
            status="completed",
        )  # type: ignore[call-arg]
