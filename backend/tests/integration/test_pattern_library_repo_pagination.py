"""Integration tests for PatternLibraryRepo.list_page keyset pagination.

Runs against the real Neo4j test container. Exercises off-by-one, tiebreaker,
filter combinations, and the soft-delete filter.
"""
from datetime import datetime

import pytest
from neo4j import AsyncDriver

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry
from explorator.services.pattern_library.filters import PatternFilters


def _entry(
    *, idx: int, score: float, genre: str = "dream_pop", ptype: str = "progression",
    source_suffix: str = "",
) -> PatternLibraryEntry:
    return PatternLibraryEntry(
        id=f"pat_{idx:04d}",
        type="pattern_library_entry",
        status="active",
        created_at=datetime(2026, 4, 19, 12, 0, 0),
        updated_at=datetime(2026, 4, 19, 12, 0, 0),
        pattern_type=ptype,
        genre=genre,
        tags=[],
        source_candidate_id=f"cand_{idx:04d}{source_suffix}",
        abstracted_pattern={},
        success_metrics={"weighted_total": score},
        notes="",
    )


async def _wipe(driver: AsyncDriver) -> None:
    async with driver.session() as neo:
        await neo.run("MATCH (p:PatternLibraryEntry) DETACH DELETE p")


@pytest.mark.asyncio
async def test_first_page_returns_limit_plus_cursor(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    # Insert 8 rows, scores 0.80 .. 0.15 descending
    for i in range(8):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    items, next_cursor = await repo.list_page(limit=5)

    assert len(items) == 5
    assert [e["success_metrics"]["weighted_total"] for e in items] == pytest.approx(
        [0.80, 0.70, 0.60, 0.50, 0.40]
    )
    assert next_cursor is not None


@pytest.mark.asyncio
async def test_cursor_round_trip_returns_next_page(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(8):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    page1, cursor1 = await repo.list_page(limit=5)
    assert cursor1 is not None

    page2, cursor2 = await repo.list_page(cursor=cursor1, limit=5)

    assert len(page2) == 3  # 8 total - 5 shown = 3 remaining
    page1_ids = {e["id"] for e in page1}
    page2_ids = {e["id"] for e in page2}
    assert page1_ids.isdisjoint(page2_ids)
    assert cursor2 is None  # terminal


@pytest.mark.asyncio
async def test_terminal_page_exact_limit_no_next_cursor(neo4j_driver: AsyncDriver) -> None:
    """Off-by-one guard: exactly `limit` rows remaining → next_cursor=None."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(5):
        await repo.upsert(_entry(idx=i, score=0.80 - i * 0.10))

    items, next_cursor = await repo.list_page(limit=5)

    assert len(items) == 5
    assert next_cursor is None


@pytest.mark.asyncio
async def test_tiebreaker_identical_weighted_total(neo4j_driver: AsyncDriver) -> None:
    """3 rows with identical weighted_total, limit=2 → no dupes, no skips across pages."""
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    for i in range(3):
        await repo.upsert(_entry(idx=i, score=0.50, source_suffix=f"_tie{i}"))

    page1, cursor = await repo.list_page(limit=2)
    assert cursor is not None
    assert len(page1) == 2

    page2, cursor2 = await repo.list_page(cursor=cursor, limit=2)
    assert len(page2) == 1
    assert cursor2 is None

    all_ids = {e["id"] for e in page1} | {e["id"] for e in page2}
    assert len(all_ids) == 3  # no dupes, no skips


@pytest.mark.asyncio
async def test_filter_by_genre_only(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, genre="dream_pop"))
    await repo.upsert(_entry(idx=2, score=0.7, genre="jazz"))

    items, _ = await repo.list_page(filters=PatternFilters(genre="dream_pop"))

    assert len(items) == 1
    assert items[0]["genre"] == "dream_pop"


@pytest.mark.asyncio
async def test_filter_by_pattern_type_only(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8, ptype="progression"))
    await repo.upsert(_entry(idx=2, score=0.7, ptype="voicing"))

    items, _ = await repo.list_page(filters=PatternFilters(pattern_type="voicing"))

    assert len(items) == 1
    assert items[0]["pattern_type"] == "voicing"


@pytest.mark.asyncio
async def test_soft_deleted_rows_hidden(neo4j_driver: AsyncDriver) -> None:
    await _wipe(neo4j_driver)
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(idx=1, score=0.8))
    await repo.upsert(_entry(idx=2, score=0.7))
    await repo.soft_delete("pat_0001")

    items, _ = await repo.list_page()

    assert len(items) == 1
    assert items[0]["id"] == "pat_0002"
