import pytest
from datetime import datetime, UTC

from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


async def _seed_arrangement(driver, arr_id, session_id="sess_test"):
    async with driver.session() as s:
        await s.run(
            "MERGE (a:ArrangementCandidate {id: $id}) "
            "SET a.session_id = $sid, a.weighted_total = 0.5",
            id=arr_id, sid=session_id,
        )


async def _seed_pattern(repo, arr_id, ptype="progression", entry_id=None):
    await repo.upsert(PatternLibraryEntry(
        id=entry_id or f"pl_deriv_{arr_id}_{ptype}",
        type="pattern_library_entry",
        status="active",
        pattern_type=ptype, genre="jazz",
        source_candidate_id=arr_id,
        success_metrics={"weighted_total": 0.8},
    ))


@pytest.mark.asyncio
async def test_fetch_curation_state_uncurated(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_u")
    await _seed_pattern(pl, "arr_deriv_u")

    state = await ac.fetch_curation_state(["arr_deriv_u"])
    assert state == {"arr_deriv_u": (False, None)}


@pytest.mark.asyncio
async def test_fetch_curation_state_curated(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_c")
    await _seed_pattern(pl, "arr_deriv_c")
    curated_at = datetime(2026, 4, 24, 14, 0, tzinfo=UTC)
    await pl.toggle_curation(arrangement_id="arr_deriv_c", is_curated=True, now=curated_at)

    state = await ac.fetch_curation_state(["arr_deriv_c"])
    is_curated, ts = state["arr_deriv_c"]
    assert is_curated is True
    assert ts == curated_at.isoformat()


@pytest.mark.asyncio
async def test_fetch_curation_state_no_library_rows_is_null(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    await _seed_arrangement(neo4j_driver, "arr_deriv_nohar")
    # No pattern rows seeded.

    state = await ac.fetch_curation_state(["arr_deriv_nohar"])
    assert state == {"arr_deriv_nohar": (None, None)}


@pytest.mark.asyncio
async def test_fetch_curation_state_batch_is_single_query(neo4j_driver):
    """N arrangements -> 1 Cypher statement (no N+1)."""
    from unittest.mock import patch

    ac = ArrangementCandidateRepo(neo4j_driver)
    pl = PatternLibraryRepo(neo4j_driver)
    for i in range(5):
        arr_id = f"arr_batch_{i}"
        await _seed_arrangement(neo4j_driver, arr_id)
        await _seed_pattern(pl, arr_id)

    ids = [f"arr_batch_{i}" for i in range(5)]
    # Count session.run invocations during fetch_curation_state.
    from neo4j import AsyncSession
    original_run = AsyncSession.run
    call_count = 0
    async def counting_run(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_run(self, *args, **kwargs)
    with patch.object(AsyncSession, "run", counting_run):
        await ac.fetch_curation_state(ids)
    assert call_count == 1, f"expected 1 query, got {call_count}"


@pytest.mark.asyncio
async def test_fetch_curation_state_empty_list(neo4j_driver):
    ac = ArrangementCandidateRepo(neo4j_driver)
    state = await ac.fetch_curation_state([])
    assert state == {}
