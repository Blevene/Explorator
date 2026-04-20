"""Neo4j repository for ArrangementCandidate nodes."""
from typing import Any

from explorator.graph.repository import BaseRepository, _neo4j_deserialize


class ArrangementCandidateRepo(BaseRepository):
    label = "ArrangementCandidate"

    async def list_finalists_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Return arrangements for a session that carry a finalist role in metadata.

        `persist_realization` stamps `metadata.role` with one of
        ``"safest" | "best_loop" | "most_experimental"`` before persisting.
        Metadata is stored as a JSON string (see `_neo4j_safe`), so we match
        on the literal ``"role"`` substring and defer dict hydration to
        `_neo4j_deserialize`.
        """
        query = """
            MATCH (a:ArrangementCandidate {session_id: $session_id})
            WHERE a.metadata IS NOT NULL
              AND a.metadata CONTAINS '"role"'
            RETURN properties(a) AS props
            ORDER BY a.weighted_total DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            records = await result.data()
            return [_neo4j_deserialize(dict(r["props"])) for r in records]

    async def get_progression_candidate(self, pc_id: str) -> dict[str, Any] | None:
        """Fetch a progression candidate by id (used during harvest reconstruction)."""
        query = """
            MATCH (p:ProgressionCandidate {id: $id})
            RETURN properties(p) AS props
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=pc_id)
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["props"]))
