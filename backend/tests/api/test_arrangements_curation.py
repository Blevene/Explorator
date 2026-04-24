"""Tests: GET /v1/candidates/{id}/arrangements and GET /v1/arrangements/{id}
expose is_curated and curated_at derived from PatternLibraryEntry state.
"""
import pytest
from datetime import datetime, UTC

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


async def _seed_candidate_and_arrangement(driver, pc_id, arr_id, session_id="sess_arr"):
    async with driver.session() as s:
        await s.run(
            "MERGE (pc:ProgressionCandidate {id: $pcid}) "
            "MERGE (a:ArrangementCandidate {id: $aid}) "
            "SET a.progression_candidate_id = $pcid, a.session_id = $sid, "
            "    a.weighted_total = 0.7, a.rank_within_round = 1",
            pcid=pc_id, aid=arr_id, sid=session_id,
        )


async def _seed_pattern(pl, arr_id, entry_id):
    await pl.upsert(PatternLibraryEntry(
        id=entry_id,
        type="pattern_library_entry",
        status="active",
        pattern_type="progression", genre="jazz",
        source_candidate_id=arr_id,
        success_metrics={"weighted_total": 0.7},
    ))


@pytest.mark.asyncio
async def test_list_arrangements_is_curated_null_when_not_harvested(
    client, neo4j_driver
):
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_null", "arr_null")
    response = await client.get("/v1/candidates/pc_null/arrangements")
    assert response.status_code == 200
    arr = next(a for a in response.json() if a["id"] == "arr_null")
    assert arr["is_curated"] is None
    assert arr["curated_at"] is None


@pytest.mark.asyncio
async def test_list_arrangements_is_curated_false_after_harvest(
    client, neo4j_driver
):
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_f", "arr_false")
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_pattern(pl, "arr_false", "pl_false_prog")
    response = await client.get("/v1/candidates/pc_f/arrangements")
    arr = next(a for a in response.json() if a["id"] == "arr_false")
    assert arr["is_curated"] is False
    assert arr["curated_at"] is None


@pytest.mark.asyncio
async def test_get_arrangement_curated_true_after_toggle(
    client, neo4j_driver
):
    await _seed_candidate_and_arrangement(neo4j_driver, "pc_t", "arr_true")
    pl = PatternLibraryRepo(neo4j_driver)
    await _seed_pattern(pl, "arr_true", "pl_true_prog")
    ts = datetime(2026, 4, 24, 16, 0, tzinfo=UTC)
    await pl.toggle_curation(arrangement_id="arr_true", is_curated=True, now=ts)

    response = await client.get("/v1/arrangements/arr_true")
    assert response.status_code == 200
    body = response.json()
    assert body["is_curated"] is True
    assert body["curated_at"] is not None
