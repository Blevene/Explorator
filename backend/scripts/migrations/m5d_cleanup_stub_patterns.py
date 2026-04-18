"""M5d migration: remove any stub PatternLibraryEntry rows with null source_candidate_id.

Pre-M5d, the model had `source_candidate_id: str | None = None`. M5d makes it required.
Any null-valued rows in dev/test Neo4j instances will fail Pydantic validation on read.
This script is idempotent and safe to run on clean databases (zero rows affected).

Usage:
    # Preview mode — shows what would be deleted, no writes.
    uv run python scripts/migrations/m5d_cleanup_stub_patterns.py

    # Destructive mode — actually deletes the null-scid rows.
    uv run python scripts/migrations/m5d_cleanup_stub_patterns.py --yes
"""
import argparse
import asyncio
import os
import sys

from explorator.graph.connection import get_driver


async def _count_legacy(driver) -> int:
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "MATCH (p:PatternLibraryEntry) WHERE p.source_candidate_id IS NULL "
            "RETURN count(p) AS n"
        )
        record = await result.single()
        return int(record["n"])


async def _delete_legacy(driver) -> int:
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "MATCH (p:PatternLibraryEntry) WHERE p.source_candidate_id IS NULL "
            "DETACH DELETE p RETURN count(p) AS removed"
        )
        record = await result.single()
        return int(record["removed"])


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d-cleanup] Target Neo4j: {uri}")

    driver = await get_driver()
    try:
        count = await _count_legacy(driver)
        if count == 0:
            print("[m5d-cleanup] No legacy null-source PatternLibraryEntry rows found. Nothing to do.")
            return 0

        if not apply:
            print(
                f"[m5d-cleanup] {count} legacy null-source PatternLibraryEntry rows would be deleted.\n"
                "[m5d-cleanup] Re-run with --yes to actually delete them."
            )
            return 0

        removed = await _delete_legacy(driver)
        print(f"[m5d-cleanup] Removed {removed} legacy PatternLibraryEntry rows")
        return 0
    finally:
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up pre-M5d null-source PatternLibraryEntry rows")
    parser.add_argument(
        "--yes", action="store_true",
        help="Actually perform the deletion. Without this flag, runs in preview mode.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
