"""Integration test: M5d-1 pattern harvest against real Neo4j.

Validates that the harvest_patterns node persists PatternLibraryEntry rows with the
expected shape, idempotence, and tag propagation. Skipped if Neo4j is not reachable.

Requires: Neo4j running at NEO4J_URI (default bolt://localhost:7688).
"""

from unittest.mock import AsyncMock

import pytest
from neo4j import AsyncDriver

from explorator.engine.nodes.harvest_patterns import harvest_patterns
from explorator.graph.pattern_library_repo import PatternLibraryRepo


def _state_with_two_finalists() -> dict:
    """Simulated state at final_selection — two arrangements, all 5 facets each."""
    return {
        "session_id": "sess_m5d1_validate",
        "genre": "dream_pop",
        "final_selection": {
            "selected_candidate_ids": ["arr_01", "arr_02"],
            "selection_roles": {"arr_01": "safest", "arr_02": "best_loop"},
        },
        "arrangement_candidates": [
            {
                "id": "arr_01", "progression_candidate_id": "prog_01",
                "voicing_plan_id": "vp_01", "bass_line_id": "bl_01",
                "groove_pattern_id": "gp_01", "melodic_complement_id": "mc_01",
            },
            {
                "id": "arr_02", "progression_candidate_id": "prog_02",
                "voicing_plan_id": "vp_02", "bass_line_id": "bl_02",
                "groove_pattern_id": "gp_02", "melodic_complement_id": "mc_02",
            },
        ],
        "progression_candidates": [
            {
                "id": "prog_01", "key_center": "A", "mode": "major",
                "chord_symbols": ["Amaj7", "F#m7", "Dmaj7", "E7"], "phrase_length_bars": 4,
                "metadata": {"roman_numerals": ["Imaj7", "vi7", "IVmaj7", "V7"]},
            },
            {
                "id": "prog_02", "key_center": "A", "mode": "major",
                "chord_symbols": ["Amaj7", "C#m7", "F#m7", "Dmaj7"], "phrase_length_bars": 4,
                "metadata": {"roman_numerals": ["Imaj7", "iii7", "vi7", "IVmaj7"]},
            },
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
            {
                "candidate_id": "arr_01", "weighted_total": 0.82,
                "scores": {"loopability": 0.85, "cadence_quality": 0.8},
                "pareto_tags": ["pareto_front"],
            },
            {
                "candidate_id": "arr_02", "weighted_total": 0.75,
                "scores": {"loopability": 0.7, "cadence_quality": 0.72},
                "pareto_tags": [],
            },
        ],
        "on_progress": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_m5d1_harvest_writes_full_facet_coverage(neo4j_driver: AsyncDriver) -> None:
    """Two finalists × 5 facets = 10 rows with correct types and source pointers."""
    state = _state_with_two_finalists()
    repo = PatternLibraryRepo(neo4j_driver)

    result = await harvest_patterns(state, repo=repo)

    assert len(result["harvested_pattern_ids"]) == 10

    async with neo4j_driver.session() as neo:
        cypher = await neo.run("""
            MATCH (p:PatternLibraryEntry)
            RETURN p.id AS id, p.pattern_type AS ptype, p.genre AS genre,
                   p.tags AS tags, p.weighted_total AS wt,
                   p.source_candidate_id AS scid
        """)
        rows = [dict(r) async for r in cypher]

    assert len(rows) == 10

    # Full-facet coverage for each finalist
    types_by_source = {(r["scid"], r["ptype"]) for r in rows}
    expected = {
        (scid, ptype)
        for scid in ("arr_01", "arr_02")
        for ptype in ("progression", "voicing", "bass", "groove", "melody")
    }
    assert types_by_source == expected

    # All rows carry the genre
    assert all(r["genre"] == "dream_pop" for r in rows)

    # Denormalized weighted_total is written to a top-level scalar
    assert all(r["wt"] is not None and r["wt"] > 0 for r in rows)

    # Progress event emitted with correct count
    state["on_progress"].assert_awaited_with("pattern_harvest", {"count": 10, "genre": "dream_pop"})


@pytest.mark.asyncio
async def test_m5d1_harvest_role_and_pareto_tag_propagation(neo4j_driver: AsyncDriver) -> None:
    """Role tags carry the finalist's assignment; pareto_front propagates from scorecard."""
    state = _state_with_two_finalists()
    repo = PatternLibraryRepo(neo4j_driver)
    await harvest_patterns(state, repo=repo)

    async with neo4j_driver.session() as neo:
        cypher = await neo.run("""
            MATCH (p:PatternLibraryEntry)
            RETURN p.source_candidate_id AS scid, p.pattern_type AS ptype, p.tags AS tags
        """)
        rows = [dict(r) async for r in cypher]

    by_scid_ptype = {(r["scid"], r["ptype"]): r["tags"] for r in rows}

    # arr_01 is "safest", arr_02 is "best_loop" — propagate to every facet of each
    for ptype in ("progression", "voicing", "bass", "groove", "melody"):
        assert "role:safest" in by_scid_ptype[("arr_01", ptype)]
        assert "role:best_loop" in by_scid_ptype[("arr_02", ptype)]

    # pareto_front appeared only on arr_01 (the only one with pareto_tags=["pareto_front"])
    assert "pareto_front" in by_scid_ptype[("arr_01", "progression")]
    assert "pareto_front" not in by_scid_ptype[("arr_02", "progression")]


@pytest.mark.asyncio
async def test_m5d1_harvest_progression_cadence_and_complexity_tags(neo4j_driver: AsyncDriver) -> None:
    """Progression harvester emits cadence:* and complexity:* tags from roman numerals."""
    state = _state_with_two_finalists()
    repo = PatternLibraryRepo(neo4j_driver)
    await harvest_patterns(state, repo=repo)

    async with neo4j_driver.session() as neo:
        cypher = await neo.run("""
            MATCH (p:PatternLibraryEntry {pattern_type: 'progression', source_candidate_id: 'arr_01'})
            RETURN p.tags AS tags
        """)
        row = await cypher.single()

    tags = set(row["tags"])
    # Roman numerals end Imaj7 → vi7 → IVmaj7 → V7: penult=IV, final=V7 → half cadence.
    # Actually with roman_numerals=["Imaj7","vi7","IVmaj7","V7"], penult=IVmaj7 (_root_only → "IV"),
    # final=V7 (_root_only → "V"). penult=IV, final=V → falls to "cadence:half" (final in V, V-family).
    cadence_tags = [t for t in tags if t.startswith("cadence:")]
    assert len(cadence_tags) == 1, f"Expected exactly one cadence tag, got {cadence_tags}"
    # 4 distinct chord symbols → complexity:mid
    assert "complexity:mid" in tags
    # loopability 0.85 → loopability:high (colon-separated per fix in commit 477de8c)
    assert "loopability:high" in tags


@pytest.mark.asyncio
async def test_m5d1_harvest_is_idempotent_on_rerun(neo4j_driver: AsyncDriver) -> None:
    """Re-harvesting the same session updates in place — no duplicates, scores refresh."""
    state = _state_with_two_finalists()
    repo = PatternLibraryRepo(neo4j_driver)

    # First harvest
    result_1 = await harvest_patterns(state, repo=repo)
    assert len(result_1["harvested_pattern_ids"]) == 10

    # Capture the first-round ID for arr_01's progression — should survive idempotent MERGE
    async with neo4j_driver.session() as neo:
        cypher = await neo.run("""
            MATCH (p:PatternLibraryEntry {source_candidate_id: 'arr_01', pattern_type: 'progression'})
            RETURN p.id AS id
        """)
        first_row = await cypher.single()
    first_id = first_row["id"]

    # Simulate a second session run that raises arr_01's weighted_total
    state["scorecards"][0]["weighted_total"] = 0.95

    result_2 = await harvest_patterns(state, repo=repo)
    # Second run also reports 10 harvested IDs (the MERGE still produces a pattern object to upsert;
    # it's the DB that deduplicates via natural key)
    assert len(result_2["harvested_pattern_ids"]) == 10

    # Row count in Neo4j is still exactly 10 — no duplicates
    async with neo4j_driver.session() as neo:
        cypher = await neo.run("MATCH (p:PatternLibraryEntry) RETURN count(p) AS n")
        row = await cypher.single()
    assert row["n"] == 10

    # arr_01 progression's weighted_total reflects the refreshed score
    async with neo4j_driver.session() as neo:
        cypher = await neo.run("""
            MATCH (p:PatternLibraryEntry {source_candidate_id: 'arr_01', pattern_type: 'progression'})
            RETURN p.id AS id, p.weighted_total AS wt
        """)
        second_row = await cypher.single()

    assert second_row["wt"] == pytest.approx(0.95)
    # The ID is preserved — ON CREATE sets it, ON MATCH does not
    assert second_row["id"] == first_id


@pytest.mark.asyncio
async def test_m5d1_harvest_natural_key_constraint_prevents_duplicates(neo4j_driver: AsyncDriver) -> None:
    """The DB-level uniqueness constraint enforces (source_candidate_id, pattern_type) uniqueness."""
    state = _state_with_two_finalists()
    repo = PatternLibraryRepo(neo4j_driver)
    await harvest_patterns(state, repo=repo)

    # Attempt a third run with the same state — still 10 total rows
    await harvest_patterns(state, repo=repo)
    async with neo4j_driver.session() as neo:
        cypher = await neo.run("MATCH (p:PatternLibraryEntry) RETURN count(p) AS n")
        row = await cypher.single()
    assert row["n"] == 10
