"""M5d-2 migration: add sort index for keyset pagination on PatternLibraryEntry.

Neo4j is schemaless, so no column creation is needed for the new `deleted_at`
property — new writes will carry it, existing rows return NULL (treated as
"not deleted" by list_page's WHERE deleted_at IS NULL filter).

This script is idempotent (IF NOT EXISTS) and safe on clean databases.

Usage:
    # Preview mode — shows what would be created.
    uv run python scripts/migrations/m5d2_pattern_library_indexes.py

    # Apply mode — actually creates the index.
    uv run python scripts/migrations/m5d2_pattern_library_indexes.py --yes
"""
import argparse
import asyncio
import os
import sys

from explorator.graph.connection import get_driver


INDEX_CYPHER = """
CREATE INDEX pattern_library_sort_idx IF NOT EXISTS
  FOR (p:PatternLibraryEntry) ON (p.weighted_total, p.id)
"""


async def _index_exists(driver) -> bool:
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "SHOW INDEXES YIELD name WHERE name = 'pattern_library_sort_idx' RETURN name"
        )
        record = await result.single()
        return record is not None


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d2-indexes] Target Neo4j: {uri}")

    driver = await get_driver()
    try:
        already = await _index_exists(driver)
        if already:
            print("[m5d2-indexes] Index pattern_library_sort_idx already exists. Nothing to do.")
            return 0

        if not apply:
            print(
                "[m5d2-indexes] Would create composite index on "
                "(:PatternLibraryEntry {weighted_total, id})."
            )
            print("[m5d2-indexes] Re-run with --yes to apply.")
            return 0

        async with driver.session() as neo_session:
            await neo_session.run(INDEX_CYPHER)
        print("[m5d2-indexes] Created pattern_library_sort_idx.")
        return 0
    finally:
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
