"""Tests for PatternLibraryRepo."""
from datetime import datetime, UTC
import pytest

from explorator.models.memory import PatternLibraryEntry
from explorator.graph.pattern_library_repo import PatternLibraryRepo


def _entry(
    *, pattern_id: str = "pl_abc", source: str = "arr_01",
    ptype: str = "progression", genre: str = "house",
    weighted_total: float = 0.82,
) -> PatternLibraryEntry:
    now = datetime.now(UTC)
    return PatternLibraryEntry(
        id=pattern_id, type="pattern_library_entry",
        created_at=now, updated_at=now, status="active", metadata={},
        pattern_type=ptype, genre=genre,
        tags=["role:safest"],
        source_candidate_id=source,
        abstracted_pattern={"chord_symbols": ["C", "F", "G", "C"]},
        success_metrics={"weighted_total": weighted_total, "loopability": 0.9},
    )


@pytest.mark.asyncio
async def test_upsert_and_get(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry())
    fetched = await repo.get_by_id("pl_abc")
    assert fetched is not None
    assert fetched["pattern_type"] == "progression"
    assert fetched["tags"] == ["role:safest"]
    assert fetched["abstracted_pattern"]["chord_symbols"] == ["C", "F", "G", "C"]
    assert fetched["weighted_total"] == pytest.approx(0.82)  # denormalized scalar


@pytest.mark.asyncio
async def test_upsert_idempotent_on_natural_key(neo4j_driver):
    """Two upserts with same (source_candidate_id, pattern_type) but different ids
    must result in exactly one row — the second call MATCHES instead of CREATING."""
    from explorator.services.pattern_library.filters import PatternFilters

    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_first", weighted_total=0.5))
    await repo.upsert(_entry(pattern_id="pl_second", weighted_total=0.9))

    filters = PatternFilters(genre="house", pattern_type="progression")
    all_rows = []
    async for entry in repo.iter_all(filters=filters):
        all_rows.append(entry)

    assert len(all_rows) == 1
    # ON MATCH SET p += $props merges in the newer props (including weighted_total)
    assert all_rows[0]["weighted_total"] == pytest.approx(0.9)
    # The id is whichever was created first (ON CREATE SET p.id = $id)
    assert all_rows[0]["id"] == "pl_first"


@pytest.mark.asyncio
async def test_delete_by_id(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry())
    await repo.delete_by_id("pl_abc")
    assert await repo.get_by_id("pl_abc") is None


@pytest.mark.asyncio
async def test_iter_all_filters_by_genre_and_type(neo4j_driver):
    from explorator.services.pattern_library.filters import PatternFilters

    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_1", source="arr_1", ptype="progression", genre="house"))
    await repo.upsert(_entry(pattern_id="pl_2", source="arr_2", ptype="voicing", genre="house"))
    await repo.upsert(_entry(pattern_id="pl_3", source="arr_3", ptype="progression", genre="techno"))

    # Test genre filter
    house_entries = []
    async for entry in repo.iter_all(filters=PatternFilters(genre="house")):
        house_entries.append(entry)
    assert len(house_entries) == 2

    # Test genre + pattern_type filter
    progression_entries = []
    async for entry in repo.iter_all(filters=PatternFilters(genre="house", pattern_type="progression")):
        progression_entries.append(entry)
    assert len(progression_entries) == 1

    # Test different genre
    techno_entries = []
    async for entry in repo.iter_all(filters=PatternFilters(genre="techno")):
        techno_entries.append(entry)
    assert len(techno_entries) == 1


@pytest.mark.asyncio
async def test_query_for_warm_starts_filters_by_tags_client_side(neo4j_driver):
    """Verify that tag filtering in query_for_warm_starts works correctly."""
    repo = PatternLibraryRepo(neo4j_driver)
    e1 = _entry(pattern_id="pl_1", source="arr_1", weighted_total=0.9)
    e1.tags = ["role:safest", "loopability:high"]
    e2 = _entry(pattern_id="pl_2", source="arr_2", weighted_total=0.8)
    e2.tags = ["role:most_experimental", "loopability:high"]
    await repo.upsert(e1)
    await repo.upsert(e2)

    # Test with role:safest filter
    safest = await repo.query_for_warm_starts(
        genre="house", top_k_per_type=5, tag_filters=["role:safest"]
    )
    assert len(safest.get("progression", [])) == 1
    assert safest["progression"][0]["id"] == "pl_1"

    # Test with loopability:high filter (both match)
    high = await repo.query_for_warm_starts(
        genre="house", top_k_per_type=5, tag_filters=["loopability:high"]
    )
    assert len(high.get("progression", [])) == 2


@pytest.mark.asyncio
async def test_query_for_warm_starts_orders_by_weighted_total(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    await repo.upsert(_entry(pattern_id="pl_low", source="arr_low", weighted_total=0.5))
    await repo.upsert(_entry(pattern_id="pl_high", source="arr_high", weighted_total=0.9))
    await repo.upsert(_entry(pattern_id="pl_mid", source="arr_mid", weighted_total=0.7))

    grouped = await repo.query_for_warm_starts(genre="house", top_k_per_type=2)

    assert [e["id"] for e in grouped["progression"]] == ["pl_high", "pl_mid"]


@pytest.mark.asyncio
async def test_query_for_warm_starts_applies_tag_filters(neo4j_driver):
    """tag_filters narrows results within each pattern_type bucket."""
    repo = PatternLibraryRepo(neo4j_driver)
    e1 = _entry(pattern_id="pl_1", source="arr_1", weighted_total=0.9)
    e1.tags = ["role:safest"]
    e2 = _entry(pattern_id="pl_2", source="arr_2", weighted_total=0.8)
    e2.tags = ["role:most_experimental"]
    await repo.upsert(e1)
    await repo.upsert(e2)

    grouped = await repo.query_for_warm_starts(
        genre="house", top_k_per_type=5, tag_filters=["role:safest"]
    )
    assert [e["id"] for e in grouped.get("progression", [])] == ["pl_1"]
