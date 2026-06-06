"""Memory-mode persistence tests for the engine nodes (driver=None).

Proves the M1 → M2 handoff and arrangement/scorecard persistence work entirely
against the in-memory MemoryStore when Neo4j is unavailable, and that the
exploration graph still compiles without a driver.
"""
from unittest.mock import MagicMock

import pytest

from explorator.engine.graph import build_exploration_graph
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.persist_round import persist_round
from explorator.models.evaluation import AggregateScorecard
from explorator.models.harmony import ProgressionCandidate
from explorator.models.realization import ArrangementCandidate
from explorator.persistence.factory import (
    make_arrangement_candidate_repo,
    make_scorecard_repo,
)
from explorator.persistence.memory_store import get_memory_store


@pytest.fixture(autouse=True)
def _clear_store():
    """Isolate each test from cross-test memory-store bleed."""
    get_memory_store().clear()
    yield
    get_memory_store().clear()


def _progression(cid: str, session_id: str = "S1") -> ProgressionCandidate:
    return ProgressionCandidate(
        id=cid,
        type="progression_candidate",
        status="generated",
        session_id=session_id,
        rationale="test",
        key_center="C",
        chord_symbols=["C", "G", "Am", "F"],
        roman_numerals=["I", "V", "vi", "IV"],
    )


def _arrangement(aid: str, pc_id: str, session_id: str = "S1") -> ArrangementCandidate:
    return ArrangementCandidate(
        id=aid,
        type="arrangement_candidate",
        status="generated",
        session_id=session_id,
        rationale="test",
        progression_candidate_id=pc_id,
    )


def _scorecard(sid: str, candidate_id: str, total: float, rank: int) -> AggregateScorecard:
    return AggregateScorecard(
        id=sid,
        type="aggregate_scorecard",
        status="active",
        candidate_id=candidate_id,
        scores={"voice_leading": total},
        weighted_total=total,
        rank_within_round=rank,
    )


async def test_persist_realization_memory_mode_stores_arrangements_and_scorecards():
    """driver=None: arrangements + their scorecards land in the MemoryStore."""
    arr1 = _arrangement("arr_1", "pc_1")
    arr2 = _arrangement("arr_2", "pc_1")
    sc1 = _scorecard("sc_1", "arr_1", 0.91, 1)
    sc2 = _scorecard("sc_2", "arr_2", 0.42, 2)

    state = {
        "session_id": "S1",
        "voicing_plans": [],
        "bass_lines": [],
        "groove_patterns": [],
        "melodic_complements": [],
        "arrangement_candidates": [
            arr1.model_dump(mode="json"),
            arr2.model_dump(mode="json"),
        ],
        "arrangement_families": [],
        "evaluations": [],
        "scorecards": [
            sc1.model_dump(mode="json"),
            sc2.model_dump(mode="json"),
        ],
        "final_selection": {
            "selection_roles": {"arr_1": "primary", "arr_2": "alternate"},
            "selected_candidate_ids": ["arr_1", "arr_2"],
        },
    }

    result = await persist_realization(state, driver=None)
    assert result == {}  # node returns an empty state delta

    arr_repo = make_arrangement_candidate_repo(None)
    sc_repo = make_scorecard_repo(None)

    stored_arrs = await arr_repo.query_by_property("session_id", "S1")
    assert {a["id"] for a in stored_arrs} == {"arr_1", "arr_2"}
    # role was stamped into metadata before persist
    by_id = {a["id"]: a for a in stored_arrs}
    assert by_id["arr_1"]["metadata"]["role"] == "primary"

    # Scorecards retrievable by candidate_id (the realization_rounds read path)
    sc_arr1 = await sc_repo.query_by_property("candidate_id", "arr_1")
    assert len(sc_arr1) == 1
    assert sc_arr1[0]["weighted_total"] == 0.91
    assert sc_arr1[0]["rank_within_round"] == 1

    sc_arr2 = await sc_repo.query_by_property("candidate_id", "arr_2")
    assert sc_arr2[0]["weighted_total"] == 0.42


async def test_persist_round_then_load_context_memory_mode_handoff():
    """M1 → M2 handoff: persist_round candidates are readable by load_context."""
    pc1 = _progression("pc_1")
    pc2 = _progression("pc_2")

    round_state = {
        "session_id": "S1",
        "genre": "dream_pop",
        "round_number": 1,
        "top_progressions": [
            pc1.model_dump(mode="json"),
            pc2.model_dump(mode="json"),
        ],
        "scorecards": [],
        "mutation_records": [],
        "provenance_events": [],
    }
    await persist_round(round_state, driver=None)

    # load_context must NOT short-circuit (no progression_candidates in state),
    # and must fetch the persisted candidates by id.
    ctx_state = {
        "progression_candidate_ids": ["pc_1", "pc_2"],
    }
    result = await load_context(ctx_state, driver=None)

    fetched_ids = {c["id"] for c in result["progression_candidates"]}
    assert fetched_ids == {"pc_1", "pc_2"}
    assert result["session_id"] == "S1"
    # genre profile served from YAML in memory mode (falls back to dream_pop)
    assert result["genre_profile"].get("genre") == "dream_pop"


def test_build_exploration_graph_compiles_without_driver():
    """build_exploration_graph(gemini, None) must compile (memory mode)."""
    graph = build_exploration_graph(MagicMock(), None)
    nodes = set(graph.get_graph().nodes)
    assert "load_context" in nodes
    assert "persist_realization" in nodes
    assert "harvest_patterns" in nodes
