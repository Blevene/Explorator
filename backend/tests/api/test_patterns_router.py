"""FastAPI TestClient tests for /v1/patterns endpoints.

Uses a real Neo4j test container (via the neo4j_driver fixture). Each test
wipes and seeds PatternLibraryEntry rows, then exercises the router.
"""
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncDriver

from explorator.api.app import create_app
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


def _entry(idx: int, score: float, genre: str = "dream_pop", ptype: str = "progression") -> PatternLibraryEntry:
    return PatternLibraryEntry(
        id=f"pat_{idx:04d}",
        type="pattern_library_entry",
        status="active",
        created_at=datetime(2026, 4, 19),
        updated_at=datetime(2026, 4, 19),
        pattern_type=ptype,
        genre=genre,
        tags=[],
        source_candidate_id=f"cand_{idx:04d}",
        abstracted_pattern={},
        success_metrics={"weighted_total": score},
        notes="",
    )


async def _wipe(driver: AsyncDriver) -> None:
    async with driver.session() as neo:
        await neo.run("MATCH (p:PatternLibraryEntry) DETACH DELETE p")


@pytest.mark.asyncio
async def test_list_patterns_returns_items_and_cursor(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(3):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?limit=2")

    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    assert "after_score" in body["next_cursor"]
    assert "after_id" in body["next_cursor"]


@pytest.mark.asyncio
async def test_list_patterns_filter_by_genre(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, genre="dream_pop"))
    await repo.upsert(_entry(idx=2, score=0.7, genre="jazz"))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?genre=jazz")

    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["genre"] == "jazz"


@pytest.mark.asyncio
async def test_list_patterns_invalid_cursor_returns_400(neo4j_driver: AsyncDriver) -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns?after_score=0.5")  # missing after_id

    assert res.status_code == 400


@pytest.mark.asyncio
async def test_get_pattern_by_id_happy_path(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns/pat_0001")

    assert res.status_code == 200
    assert res.json()["id"] == "pat_0001"


@pytest.mark.asyncio
async def test_get_pattern_by_id_missing_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/patterns/pat_missing")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_then_get_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_del = await client.delete("/v1/patterns/pat_0001")
        assert res_del.status_code == 204

        res_get = await client.get("/v1/patterns/pat_0001")
        assert res_get.status_code == 404


@pytest.mark.asyncio
async def test_delete_twice_returns_404(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.delete("/v1/patterns/pat_0001")).status_code == 204
        assert (await client.delete("/v1/patterns/pat_0001")).status_code == 404


@pytest.mark.asyncio
async def test_re_upsert_resurrects_soft_deleted(neo4j_driver: AsyncDriver) -> None:
    """Upsert with same natural key clears deleted_at (MERGE ON MATCH SET deleted_at = NULL)."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))
    await repo.soft_delete("pat_0001")
    assert await repo.get_by_id("pat_0001") is None  # hidden

    # Re-upsert (simulating re-harvest)
    await repo.upsert(_entry(idx=1, score=0.9))

    restored = await repo.get_by_id("pat_0001")
    assert restored is not None
    assert restored["id"] == "pat_0001"
    assert restored["success_metrics"]["weighted_total"] == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_list_patterns_response_includes_curation_fields(neo4j_driver: AsyncDriver) -> None:
    """GET /v1/patterns response items carry is_curated + curated_at."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(PatternLibraryEntry(
        id="pl_schema_test",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_curation_schema",
        success_metrics={"weighted_total": 0.5},
    ))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/patterns")

    assert response.status_code == 200
    items = response.json()["items"]
    match = next(i for i in items if i["source_candidate_id"] == "cand_curation_schema")
    assert match["is_curated"] is False
    assert match["curated_at"] is None
