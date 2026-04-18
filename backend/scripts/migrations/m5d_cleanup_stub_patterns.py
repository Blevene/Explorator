"""M5d migration: remove any stub PatternLibraryEntry rows with null source_candidate_id.

Pre-M5d, the model had `source_candidate_id: str | None = None`. M5d makes it required.
Any null-valued rows in dev/test Neo4j instances will fail Pydantic validation on read.
This script is idempotent and safe to run on clean databases (zero rows affected).
"""
import asyncio

from explorator.graph.connection import get_driver


async def main() -> None:
    driver = await get_driver()
    async with driver.session() as neo_session:
        result = await neo_session.run(
            "MATCH (p:PatternLibraryEntry) WHERE p.source_candidate_id IS NULL "
            "DETACH DELETE p RETURN count(p) AS removed"
        )
        record = await result.single()
        print(f"Removed {record['removed']} legacy PatternLibraryEntry rows")


if __name__ == "__main__":
    asyncio.run(main())
