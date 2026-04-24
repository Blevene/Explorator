"""M5d-3 migration: backfill is_curated=false on existing PatternLibraryEntry
rows and create a feedback-event filtering index.

Neo4j is schemaless; new writes carry `is_curated` / `curated_at` via model
defaults. This script only matters for pre-existing rows harvested before
M5d-3 landed — they need `is_curated=false` set explicitly so
`WHERE p.is_curated = true` filter queries behave correctly.

Idempotent (IF NOT EXISTS + IS NULL guards).

Usage:
    # Preview.
    uv run python scripts/migrations/m5d3_curation_fields.py

    # Apply.
    uv run python scripts/migrations/m5d3_curation_fields.py --yes
"""
import argparse
import asyncio
import os
import sys

from explorator.graph.connection import get_driver


BACKFILL_CYPHER = """
MATCH (p:PatternLibraryEntry)
WHERE p.is_curated IS NULL
SET p.is_curated = false
RETURN count(p) AS updated
"""

INDEX_CYPHER = """
CREATE INDEX user_feedback_event_type IF NOT EXISTS
  FOR (n:UserFeedbackEvent) ON (n.feedback_type, n.candidate_id)
"""


async def main(apply: bool) -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    print(f"[m5d3-curation] Target Neo4j: {uri}")
    if not apply:
        print("[m5d3-curation] Dry-run. Would execute:")
        print(BACKFILL_CYPHER)
        print(INDEX_CYPHER)
        return 0

    driver = await get_driver()
    try:
        async with driver.session() as neo_session:
            result = await neo_session.run(BACKFILL_CYPHER)
            record = await result.single()
            updated = record["updated"] if record else 0
            print(f"[m5d3-curation] Backfilled is_curated=false on {updated} rows.")
            await neo_session.run(INDEX_CYPHER)
            print("[m5d3-curation] Created index user_feedback_event_type (if not exists).")
        return 0
    finally:
        await driver.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="apply the migration")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(apply=args.yes)))
