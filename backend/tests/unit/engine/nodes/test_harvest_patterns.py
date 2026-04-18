"""Tests for harvest_patterns LangGraph node."""
import logging
from unittest.mock import AsyncMock

import pytest

from explorator.engine.nodes.harvest_patterns import harvest_patterns


def _state_with_one_finalist() -> dict:
    return {
        "session_id": "sess_01",
        "genre": "house",
        "final_selection": {
            "selected_candidate_ids": ["arr_01"],
            "selection_roles": {"arr_01": "safest"},
        },
        "arrangement_candidates": [{
            "id": "arr_01",
            "progression_candidate_id": "prog_01",
            "voicing_plan_id": "vp_01",
            "bass_line_id": "bl_01",
            "groove_pattern_id": "gp_01",
            "melodic_complement_id": "mc_01",
        }],
        "progression_candidates": [{
            "id": "prog_01", "key_center": "C", "mode": "major",
            "chord_symbols": ["C", "F", "G", "C"], "phrase_length_bars": 4,
            "metadata": {"roman_numerals": ["I", "IV", "V", "I"]},
        }],
        "voicing_plans": [{"id": "vp_01", "strategy": {"register_profile": "mid", "density": "medium", "voice_count": 4}}],
        "bass_lines": [{"id": "bl_01", "mode": "walking", "rhythmic_density": 0.6}],
        "groove_patterns": [{"id": "gp_01", "swing_level": 0.3, "syncopation_level": 0.4, "density": 0.6, "template_name": "house_basic"}],
        "melodic_complements": [{"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 14, "rhythmic_density": 0.5}}],
        "scorecards": [{"candidate_id": "arr_01", "weighted_total": 0.8, "scores": {"loopability": 0.8}, "pareto_tags": []}],
        "on_progress": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_harvest_patterns_persists_one_entry_per_facet():
    state = _state_with_one_finalist()
    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)
    assert repo.upsert.await_count == 5
    assert len(result["harvested_pattern_ids"]) == 5
    # Lifecycle events (node_started, node_completed) bracket the domain pattern_harvest event
    progress_calls = [call.args for call in state["on_progress"].await_args_list]
    assert progress_calls[0] == ("node_started", {"node": "harvest_patterns"})
    assert ("pattern_harvest", {"count": 5, "genre": "house"}) in progress_calls
    assert progress_calls[-1] == ("node_completed", {"node": "harvest_patterns", "count": 5})


@pytest.mark.asyncio
async def test_harvest_patterns_continues_after_single_upsert_failure(caplog):
    """A transient Neo4j error on one facet must not abort the other 4."""
    state = _state_with_one_finalist()
    repo = AsyncMock()
    repo.upsert.side_effect = [RuntimeError("neo4j blip"), None, None, None, None]
    with caplog.at_level(logging.ERROR):
        result = await harvest_patterns(state, repo=repo)
    assert repo.upsert.await_count == 5
    assert len(result["harvested_pattern_ids"]) == 4  # one failure excluded
    assert any("harvest_patterns: failed to upsert" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_harvest_patterns_skips_when_no_final_selection():
    state = {"session_id": "sess_01", "genre": "house", "final_selection": {"selected_candidate_ids": []}}
    repo = AsyncMock()
    result = await harvest_patterns(state, repo=repo)
    repo.upsert.assert_not_awaited()
    assert result["harvested_pattern_ids"] == []


@pytest.mark.asyncio
async def test_harvest_patterns_emits_lifecycle_even_when_no_finalists():
    """Lifecycle events must fire even when there's nothing to harvest,
    so the UI progress indicator can transition through harvest_patterns correctly."""
    state = {
        "session_id": "sess_01", "genre": "house",
        "final_selection": {"selected_candidate_ids": []},
        "on_progress": AsyncMock(),
    }
    repo = AsyncMock()
    await harvest_patterns(state, repo=repo)
    progress_calls = [call.args for call in state["on_progress"].await_args_list]
    assert progress_calls == [
        ("node_started", {"node": "harvest_patterns"}),
        ("node_completed", {"node": "harvest_patterns", "count": 0}),
    ]
