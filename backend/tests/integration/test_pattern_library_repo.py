"""Tests for PatternLibraryRepo."""

from datetime import UTC, datetime

import pytest

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.models.memory import PatternLibraryEntry


def _entry(
    *,
    pattern_id: str = "pl_abc",
    source: str = "arr_01",
    ptype: str = "progression",
    genre: str = "house",
    weighted_total: float = 0.82,
) -> PatternLibraryEntry:
    now = datetime.now(UTC)
    return PatternLibraryEntry(
        id=pattern_id,
        type="pattern_library_entry",
        created_at=now,
        updated_at=now,
        status="active",
        metadata={},
        pattern_type=ptype,
        genre=genre,
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
    await repo.upsert(
        _entry(pattern_id="pl_3", source="arr_3", ptype="progression", genre="techno")
    )

    # Test genre filter
    house_entries = []
    async for entry in repo.iter_all(filters=PatternFilters(genre="house")):
        house_entries.append(entry)
    assert len(house_entries) == 2

    # Test genre + pattern_type filter
    progression_entries = []
    async for entry in repo.iter_all(
        filters=PatternFilters(genre="house", pattern_type="progression")
    ):
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


def _curated_entry(**overrides):
    defaults = dict(
        id="pl_curated_test",
        type="pattern_library_entry",
        status="active",
        pattern_type="progression",
        genre="jazz",
        source_candidate_id="cand_curate_preserve",
        success_metrics={"weighted_total": 0.8},
    )
    defaults.update(overrides)
    return PatternLibraryEntry(**defaults)


@pytest.mark.asyncio
async def test_upsert_on_match_preserves_curation_fields(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    # First harvest.
    entry = _curated_entry()
    await repo.upsert(entry)
    # Simulate user curation by mutating state directly (the repo.toggle_curation
    # method lands in Task 5; this test pins the upsert invariant independently).
    curated_at = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    async with neo4j_driver.session() as s:
        await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) "
            "SET p.is_curated = true, p.curated_at = $ts",
            scid=entry.source_candidate_id,
            pt=entry.pattern_type,
            ts=curated_at.isoformat(),
        )
    # Re-harvest — Pydantic default is_curated=False must NOT wipe curation.
    reharvested = _curated_entry(success_metrics={"weighted_total": 0.9})
    await repo.upsert(reharvested)

    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: $pt}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at, "
            "       p.weighted_total AS weighted_total",
            scid=entry.source_candidate_id,
            pt=entry.pattern_type,
        )
        record = await result.single()
    assert record["is_curated"] is True, "curation cleared by re-harvest"
    assert record["curated_at"] == curated_at.isoformat()
    assert record["weighted_total"] == pytest.approx(0.9)  # new metrics did land


@pytest.mark.asyncio
async def test_upsert_on_create_defaults_curation(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    entry = _curated_entry(source_candidate_id="cand_create_default")
    await repo.upsert(entry)
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=entry.source_candidate_id,
        )
        record = await result.single()
    assert record["is_curated"] is False
    assert record["curated_at"] is None


from explorator.utils import utc_now


@pytest.mark.asyncio
async def test_toggle_curation_updates_all_facets(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_multi"
    # Seed 3 facets for the same arrangement.
    for ptype in ("progression", "voicing", "bass"):
        await repo.upsert(
            _curated_entry(
                id=f"pl_toggle_{ptype}",
                source_candidate_id=scid,
                pattern_type=ptype,
            )
        )
    now = datetime(2026, 4, 24, 13, 0, tzinfo=UTC)

    affected = await repo.toggle_curation(arrangement_id=scid, is_curated=True, now=now)

    assert len(affected) == 3
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.id AS id, p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=scid,
        )
        rows = await result.data()
    assert all(r["is_curated"] is True for r in rows)
    assert all(r["curated_at"] == now.isoformat() for r in rows)


@pytest.mark.asyncio
async def test_toggle_curation_uncurate_clears_curated_at(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_uncurate"
    await repo.upsert(_curated_entry(id="pl_toggle_unc", source_candidate_id=scid))
    await repo.toggle_curation(
        arrangement_id=scid,
        is_curated=True,
        now=datetime(2026, 4, 24, 13, 0, tzinfo=UTC),
    )
    affected = await repo.toggle_curation(
        arrangement_id=scid,
        is_curated=False,
        now=datetime(2026, 4, 24, 13, 5, tzinfo=UTC),
    )
    assert len(affected) == 1
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid}) "
            "RETURN p.is_curated AS is_curated, p.curated_at AS curated_at",
            scid=scid,
        )
        record = await result.single()
    assert record["is_curated"] is False
    assert record["curated_at"] is None


@pytest.mark.asyncio
async def test_toggle_curation_skips_soft_deleted(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    scid = "cand_toggle_softdel"
    await repo.upsert(
        _curated_entry(
            id="pl_softdel_prog",
            source_candidate_id=scid,
            pattern_type="progression",
        )
    )
    await repo.upsert(
        _curated_entry(
            id="pl_softdel_voic",
            source_candidate_id=scid,
            pattern_type="voicing",
        )
    )

    # Soft-delete one facet.
    async with neo4j_driver.session() as s:
        result = await s.run(
            "MATCH (p:PatternLibraryEntry {source_candidate_id: $scid, pattern_type: 'voicing'}) "
            "RETURN p.id AS id",
            scid=scid,
        )
        deleted_id = (await result.single())["id"]
    await repo.soft_delete(deleted_id)

    affected = await repo.toggle_curation(
        arrangement_id=scid,
        is_curated=True,
        now=utc_now(),
    )
    assert len(affected) == 1
    assert deleted_id not in affected


@pytest.mark.asyncio
async def test_toggle_curation_empty_arrangement_returns_empty(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    affected = await repo.toggle_curation(
        arrangement_id="cand_nonexistent",
        is_curated=True,
        now=utc_now(),
    )
    assert affected == []


from explorator.services.pattern_library.filters import PatternFilters


@pytest.mark.asyncio
async def test_list_page_curated_only_filter(neo4j_driver):
    repo = PatternLibraryRepo(neo4j_driver)
    # Seed: one curated arrangement, one uncurated.
    for scid, curate in (("cand_filter_c1", True), ("cand_filter_c2", False)):
        await repo.upsert(
            _curated_entry(
                id=f"pl_filter_{scid}",
                source_candidate_id=scid,
                pattern_type="progression",
            )
        )
        if curate:
            await repo.toggle_curation(
                arrangement_id=scid,
                is_curated=True,
                now=utc_now(),
            )

    # curated_only=False -> both visible.
    all_items, _ = await repo.list_page(filters=PatternFilters(), limit=50)
    ids_all = {e["source_candidate_id"] for e in all_items}
    assert "cand_filter_c1" in ids_all
    assert "cand_filter_c2" in ids_all

    # curated_only=True -> only curated.
    curated_items, _ = await repo.list_page(
        filters=PatternFilters(curated_only=True),
        limit=50,
    )
    ids_curated = {e["source_candidate_id"] for e in curated_items}
    assert "cand_filter_c1" in ids_curated
    assert "cand_filter_c2" not in ids_curated


@pytest.mark.asyncio
async def test_list_page_cursor_stable_across_curated_only_toggle(neo4j_driver):
    """Cursor emitted under one filter regime is still valid under the other.

    The cursor encodes (weighted_total, id) only; it does not embed the filter
    set, so paginating with the same cursor across a filter toggle must just
    re-apply the new filter — never 500 or produce inconsistent ordering.
    """
    repo = PatternLibraryRepo(neo4j_driver)
    # Seed 6 entries, alternating curated/uncurated, strictly-descending score.
    for i in range(6):
        scid = f"cand_cursor_{i}"
        await repo.upsert(
            _curated_entry(
                id=f"pl_cursor_{i}",
                source_candidate_id=scid,
                pattern_type="progression",
                success_metrics={"weighted_total": 0.9 - (i * 0.1)},
            )
        )
        if i % 2 == 0:
            await repo.toggle_curation(
                arrangement_id=scid,
                is_curated=True,
                now=utc_now(),
            )

    # Page 1 with no filter -> 2 items, cursor returned.
    items1, cursor1 = await repo.list_page(
        filters=PatternFilters(),
        limit=2,
    )
    assert cursor1 is not None
    assert len(items1) == 2

    # Page 2 with curated_only=True using the same cursor -> no crash, only
    # curated items that come AFTER the cursor returned.
    items2, _ = await repo.list_page(
        filters=PatternFilters(curated_only=True),
        cursor=cursor1,
        limit=10,
    )
    assert all(i["is_curated"] is True for i in items2)
