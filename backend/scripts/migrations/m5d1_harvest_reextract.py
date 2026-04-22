"""M5d-1 migration: re-extract abstracted_pattern + tags for existing library rows.

The M5d-1 harvest extractors read from wrong field paths on their source nodes
(see docs/manual-test/m5d2-pattern-library.md for the full table). This script
walks every PatternLibraryEntry, refetches its source arrangement + facet node,
and re-runs the (now correct) extractor, updating abstracted_pattern + tags in
place. ULID id and created_at are preserved.

Idempotent: re-running produces identical output for already-reharvested rows
(modulo updated_at). Safe to run on clean databases (zero rows affected).

Usage:
    # Preview mode — reports counts and shows a sample diff for up to 3 rows.
    uv run python scripts/migrations/m5d1_harvest_reextract.py

    # Apply mode — actually updates rows in Neo4j.
    uv run python scripts/migrations/m5d1_harvest_reextract.py --yes
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

from explorator.domain.memory.pattern_harvesting import (
    harvest_bass_pattern,
    harvest_groove_pattern,
    harvest_melody_pattern,
    harvest_progression_pattern,
    harvest_voicing_pattern,
)
from explorator.graph.connection import get_driver
from explorator.graph.repository import _neo4j_deserialize
from explorator.utils import utc_now

logger = logging.getLogger(__name__)


# Arrangement field that points at the facet node, by pattern_type.
_FACET_POINTER = {
    "voicing": "voicing_plan_id",
    "bass": "bass_line_id",
    "groove": "groove_pattern_id",
    "melody": "melodic_complement_id",
    # progression is fetched via arrangement.progression_candidate_id (below).
}

# Neo4j label of the facet node, by pattern_type.
_FACET_LABEL = {
    "progression": "ProgressionCandidate",
    "voicing": "VoicingPlan",
    "bass": "BassLine",
    "groove": "GroovePattern",
    "melody": "MelodicComplement",
}


async def _load_node(driver, label: str, node_id: str) -> dict[str, Any] | None:
    query = f"MATCH (n:{label} {{id: $id}}) RETURN properties(n) AS props"
    async with driver.session() as session:
        result = await session.run(query, id=node_id)
        rec = await result.single()
    if rec is None:
        return None
    return _neo4j_deserialize(dict(rec["props"]))


def _role_from_tags(tags: list[str]) -> str:
    for t in tags or []:
        if t.startswith("role:"):
            return t.removeprefix("role:")
    return "unknown"


def _scorecard_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct a scorecard dict from the stored entry so the extractor can
    rebuild tags without having to refetch the original scoring pass."""
    metrics = entry.get("success_metrics") or {}
    weighted_total = metrics.get("weighted_total") or 0.0
    scores = {k: v for k, v in metrics.items() if k != "weighted_total"}
    pareto = ["pareto_front"] if "pareto_front" in (entry.get("tags") or []) else []
    return {"weighted_total": weighted_total, "scores": scores, "pareto_tags": pareto}


def _reextract(
    *,
    entry: dict[str, Any],
    arrangement: dict[str, Any],
    facet: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Dispatch to the correct extractor by pattern_type; return (abstracted, tags)."""
    ptype = entry["pattern_type"]
    scorecard = _scorecard_from_entry(entry)
    role = _role_from_tags(entry.get("tags") or [])
    genre = entry.get("genre") or ""

    if ptype == "progression":
        refreshed = harvest_progression_pattern(
            arrangement=arrangement, progression=facet,
            scorecard=scorecard, genre=genre, role=role,
        )
    elif ptype == "voicing":
        refreshed = harvest_voicing_pattern(
            arrangement=arrangement, voicing_plan=facet,
            scorecard=scorecard, genre=genre, role=role,
        )
    elif ptype == "bass":
        refreshed = harvest_bass_pattern(
            arrangement=arrangement, bass_line=facet,
            scorecard=scorecard, genre=genre, role=role,
        )
    elif ptype == "groove":
        refreshed = harvest_groove_pattern(
            arrangement=arrangement, groove=facet,
            scorecard=scorecard, genre=genre, role=role,
        )
    elif ptype == "melody":
        refreshed = harvest_melody_pattern(
            arrangement=arrangement, melody=facet,
            scorecard=scorecard, genre=genre, role=role,
        )
    else:
        raise ValueError(f"unknown pattern_type: {ptype}")
    return refreshed.abstracted_pattern, refreshed.tags


async def _iter_all_entries(driver):
    """Yield every PatternLibraryEntry (including soft-deleted) as a deserialized dict."""
    query = "MATCH (p:PatternLibraryEntry) RETURN properties(p) AS props"
    async with driver.session() as session:
        result = await session.run(query)
        async for record in result:
            yield _neo4j_deserialize(dict(record["props"]))


async def _apply_update(
    driver,
    *,
    entry_id: str,
    abstracted: dict[str, Any],
    tags: list[str],
) -> None:
    query = """
    MATCH (p:PatternLibraryEntry {id: $id})
    SET p.abstracted_pattern = $abstracted,
        p.tags = $tags,
        p.updated_at = $now
    """
    async with driver.session() as session:
        await session.run(
            query,
            id=entry_id,
            abstracted=json.dumps(abstracted),
            tags=tags,
            now=utc_now().isoformat(),
        )


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d1-reextract] Target Neo4j: {uri}")
    print(f"[m5d1-reextract] Mode: {'APPLY' if apply else 'dry-run'}")

    driver = await get_driver()
    updated = 0
    skipped_missing_arrangement = 0
    skipped_missing_facet = 0
    errors = 0
    samples_shown = 0

    try:
        arrangements_cache: dict[str, dict[str, Any] | None] = {}
        facet_cache: dict[tuple[str, str], dict[str, Any] | None] = {}

        async for entry in _iter_all_entries(driver):
            entry_id = entry["id"]
            ptype = entry["pattern_type"]
            scid = entry.get("source_candidate_id")
            if not scid:
                # Shouldn't happen post-M5d_cleanup_stub; log and skip.
                skipped_missing_arrangement += 1
                continue

            if scid not in arrangements_cache:
                arrangements_cache[scid] = await _load_node(driver, "ArrangementCandidate", scid)
            arrangement = arrangements_cache[scid]
            if arrangement is None:
                skipped_missing_arrangement += 1
                continue

            # Resolve the facet node id for this pattern_type.
            if ptype == "progression":
                facet_id = arrangement.get("progression_candidate_id")
            else:
                facet_id = arrangement.get(_FACET_POINTER.get(ptype, ""))

            if not facet_id:
                skipped_missing_facet += 1
                continue

            label = _FACET_LABEL.get(ptype)
            if label is None:
                errors += 1
                logger.warning("[m5d1-reextract] unknown pattern_type=%s on entry %s", ptype, entry_id)
                continue

            key = (label, facet_id)
            if key not in facet_cache:
                facet_cache[key] = await _load_node(driver, label, facet_id)
            facet = facet_cache[key]
            if facet is None:
                skipped_missing_facet += 1
                continue

            try:
                new_abstracted, new_tags = _reextract(
                    entry=entry, arrangement=arrangement, facet=facet,
                )
            except Exception as exc:  # noqa: BLE001 — surface per-row errors, continue loop
                errors += 1
                logger.exception(
                    "[m5d1-reextract] re-extract failed for %s (%s): %s",
                    entry_id, ptype, exc,
                )
                continue

            # Dry-run: show up to 3 before/after samples, one per pattern_type
            # where possible, then just counts.
            if not apply and samples_shown < 3:
                before = entry.get("abstracted_pattern") or {}
                print(f"\n[m5d1-reextract] SAMPLE {samples_shown + 1} — {entry_id} ({ptype})")
                print(f"  BEFORE abstracted: {json.dumps(before, sort_keys=True)}")
                print(f"  AFTER  abstracted: {json.dumps(new_abstracted, sort_keys=True)}")
                print(f"  BEFORE tags:       {sorted(entry.get('tags') or [])}")
                print(f"  AFTER  tags:       {sorted(new_tags)}")
                samples_shown += 1

            if apply:
                await _apply_update(
                    driver, entry_id=entry_id,
                    abstracted=new_abstracted, tags=new_tags,
                )
            updated += 1

        print(
            f"\n[m5d1-reextract] {'Updated' if apply else 'Would update'} {updated} rows. "
            f"Skipped {skipped_missing_arrangement} (no arrangement), "
            f"{skipped_missing_facet} (no facet node). Errors: {errors}."
        )
        if not apply:
            print("[m5d1-reextract] Re-run with --yes to apply.")
        return 0 if errors == 0 else 1
    finally:
        await driver.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Re-extract abstracted_pattern + tags for PatternLibraryEntry rows")
    parser.add_argument("--yes", action="store_true", help="Actually apply updates (default: dry-run preview).")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
