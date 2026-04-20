"""Unit tests for harvest_session_finalists_from_state.

Uses the same state-shape fixture as test_m5d1_harvest.py but at the helper level,
so the helper is exercised without any LangGraph or SSE plumbing.
"""
from unittest.mock import AsyncMock

import pytest

from explorator.services.pattern_library.harvest_service import (
    HarvestReport,
    SkipReason,
    harvest_session_finalists_from_state,
)


def _state_with_two_finalists() -> dict:
    """Same shape as backend/tests/integration/test_m5d1_harvest.py builder."""
    return {
        "session_id": "sess_harvest_helper",
        "genre": "dream_pop",
        "final_selection": {
            "selected_candidate_ids": ["arr_01", "arr_02"],
            "selection_roles": {"arr_01": "safest", "arr_02": "best_loop"},
        },
        "arrangement_candidates": [
            {"id": "arr_01", "progression_candidate_id": "prog_01",
             "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
             "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01"},
            {"id": "arr_02", "progression_candidate_id": "prog_02",
             "voicing_plan_id": "vp_02", "bass_line_id": "bl_02",
             "groove_pattern_id": "gp_02", "melodic_complement_id": "mc_02"},
        ],
        "progression_candidates": [
            {"id": "prog_01", "key_center": "A", "mode": "major",
             "chord_symbols": ["Amaj7", "F#m7", "Dmaj7", "E7"], "phrase_length_bars": 4,
             "metadata": {"roman_numerals": ["Imaj7", "vi7", "IVmaj7", "V7"]}},
            {"id": "prog_02", "key_center": "A", "mode": "major",
             "chord_symbols": ["Amaj7", "C#m7", "F#m7", "Dmaj7"], "phrase_length_bars": 4,
             "metadata": {"roman_numerals": ["Imaj7", "iii7", "vi7", "IVmaj7"]}},
        ],
        "voicing_plans": [
            {"id": "vp_01", "strategy": {"register_profile": "mid_high", "density": "medium", "voice_count": 4}},
            {"id": "vp_02", "strategy": {"register_profile": "mid_high", "density": "medium", "voice_count": 4}},
        ],
        "bass_lines": [
            {"id": "bl_01", "mode": "root", "rhythmic_density": 0.4},
            {"id": "bl_02", "mode": "walking", "rhythmic_density": 0.6},
        ],
        "groove_patterns": [
            {"id": "gp_01", "swing_level": 0.3, "syncopation_level": 0.2, "density": 0.5, "template_name": "dream_pop_basic"},
            {"id": "gp_02", "swing_level": 0.5, "syncopation_level": 0.4, "density": 0.7, "template_name": "dream_pop_dense"},
        ],
        "melodic_complements": [
            {"id": "mc_01", "strategy": {"contour_type": "arch", "range_semitones": 12, "rhythmic_density": 0.4}},
            {"id": "mc_02", "strategy": {"contour_type": "descending", "range_semitones": 19, "rhythmic_density": 0.5}},
        ],
        "scorecards": [
            {"candidate_id": "arr_01", "weighted_total": 0.82,
             "scores": {"loopability": 0.85, "cadence_quality": 0.8},
             "pareto_tags": ["pareto_front"]},
            {"candidate_id": "arr_02", "weighted_total": 0.75,
             "scores": {"loopability": 0.7, "cadence_quality": 0.72},
             "pareto_tags": []},
        ],
    }


@pytest.mark.asyncio
async def test_happy_path_upserts_ten_patterns() -> None:
    """2 finalists × 5 facets = 10 upserts; HarvestReport reflects that."""
    repo = AsyncMock()
    repo.upsert = AsyncMock()

    report = await harvest_session_finalists_from_state(
        _state_with_two_finalists(), pattern_library_repo=repo
    )

    assert isinstance(report, HarvestReport)
    assert report.session_id == "sess_harvest_helper"
    assert report.upserted_count == 10
    assert len(report.upserted_pattern_ids) == 10
    assert report.skipped_count == 0
    assert report.skipped_reasons == []
    assert repo.upsert.await_count == 10


@pytest.mark.asyncio
async def test_no_finalists_returns_empty_report() -> None:
    """Empty selected_candidate_ids short-circuits; no upserts attempted."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    state["final_selection"]["selected_candidate_ids"] = []

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    assert report.upserted_count == 0
    assert report.upserted_pattern_ids == []
    assert repo.upsert.await_count == 0


@pytest.mark.asyncio
async def test_missing_genre_skips_harvest() -> None:
    """No genre → skip harvest (polluting the library with 'unknown' genre is worse than skipping)."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    del state["genre"]

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    assert report.upserted_count == 0
    assert report.skipped_count >= 1
    assert all(e.reason == SkipReason.MISSING_GENRE for e in report.skipped_reasons)
    assert repo.upsert.await_count == 0


@pytest.mark.asyncio
async def test_missing_arrangement_records_skip_reason() -> None:
    """A selected_id with no matching arrangement is recorded, not silently dropped."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    state["arrangement_candidates"] = [state["arrangement_candidates"][0]]
    # arr_02 selected but not present in arrangement_candidates

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo
    )

    # arr_01 still produces 5 upserts
    assert report.upserted_count == 5
    # arr_02 produces a single MISSING_ARRANGEMENT skip (not 5, since we can't
    # know which pattern_types would have applied without the arrangement)
    arr02_skips = [e for e in report.skipped_reasons if e.candidate_id == "arr_02"]
    assert len(arr02_skips) == 1
    assert arr02_skips[0].reason == SkipReason.MISSING_ARRANGEMENT


@pytest.mark.asyncio
async def test_missing_progression_records_skip_reason() -> None:
    """Arrangement exists but its progression is absent → MISSING_PROGRESSION skip."""
    repo = AsyncMock()
    state = _state_with_two_finalists()
    # Remove arr_02's progression; arr_02 still selected
    state["progression_candidates"] = [state["progression_candidates"][0]]

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo,
    )

    # arr_01 still produces 5 upserts (its progression is present)
    assert report.upserted_count == 5
    # arr_02 produces a single MISSING_PROGRESSION skip
    arr02_skips = [e for e in report.skipped_reasons if e.candidate_id == "arr_02"]
    assert len(arr02_skips) == 1
    assert arr02_skips[0].reason == SkipReason.MISSING_PROGRESSION


@pytest.mark.asyncio
async def test_upsert_failure_recorded_in_skip_reasons() -> None:
    """Neo4jError from repo.upsert is caught and recorded as UPSERT_FAILED;
    sibling upserts continue."""
    from neo4j.exceptions import Neo4jError

    repo = AsyncMock()
    # First call fails; subsequent calls succeed
    call_count = {"n": 0}

    async def flaky_upsert(_entry):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise Neo4jError("simulated failure")

    repo.upsert = flaky_upsert

    report = await harvest_session_finalists_from_state(
        _state_with_two_finalists(), pattern_library_repo=repo,
    )

    # One failure, 9 successes
    assert report.upserted_count == 9
    assert report.skipped_count == 1
    assert report.skipped_reasons[0].reason == SkipReason.UPSERT_FAILED


@pytest.mark.asyncio
async def test_idempotence_via_repo_upsert() -> None:
    """Running twice on the same state upserts the same count and same natural keys.

    At the helper level, upserted_pattern_ids are fresh each run (new ULIDs); the
    (source_candidate_id, pattern_type) pairs on the upsert calls are what's
    stable. Idempotence at the ID level is a repo/DB concern — it's covered in
    the existing M5d-1 integration test against real Neo4j.
    """
    state = _state_with_two_finalists()

    repo_a = AsyncMock()
    repo_a.upsert = AsyncMock()
    report_a = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo_a,
    )

    repo_b = AsyncMock()
    repo_b.upsert = AsyncMock()
    report_b = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo_b,
    )

    assert report_a.upserted_count == report_b.upserted_count == 10

    # Same set of (source_candidate_id, pattern_type) pairs hits the repo each run.
    keys_a = {
        (call.args[0].source_candidate_id, call.args[0].pattern_type)
        for call in repo_a.upsert.await_args_list
    }
    keys_b = {
        (call.args[0].source_candidate_id, call.args[0].pattern_type)
        for call in repo_b.upsert.await_args_list
    }
    assert keys_a == keys_b
    assert len(keys_a) == 10
