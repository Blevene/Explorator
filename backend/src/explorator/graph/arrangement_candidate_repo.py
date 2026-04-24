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

    async def fetch_curation_state(
        self, arrangement_ids: list[str]
    ) -> dict[str, tuple[bool | None, str | None]]:
        """Batch-fetch (is_curated, curated_at) for the given arrangements.

        Single-round-trip LEFT-JOIN derivation per M5d-3 spec. Returns a dict
        keyed by arrangement_id with `(is_curated, curated_at_iso)`. A tuple
        value of `(None, None)` means no non-deleted PatternLibraryEntry
        exists for the arrangement — treat as "not yet harvested." Since
        arrangement-level fan-out keeps facet rows in sync, any single row is
        the source of truth for the arrangement's curation state.
        """
        if not arrangement_ids:
            return {}
        query = """
        UNWIND $arrangement_ids AS aid
        MATCH (a:ArrangementCandidate {id: aid})
        OPTIONAL MATCH (p:PatternLibraryEntry)
          WHERE p.source_candidate_id = a.id AND p.deleted_at IS NULL
        WITH a, head(collect(p)) AS p
        RETURN a.id AS arrangement_id,
               p.is_curated AS is_curated,
               p.curated_at AS curated_at
        """
        async with self.driver.session() as session:
            result = await session.run(query, arrangement_ids=arrangement_ids)
            records = await result.data()
        return {
            r["arrangement_id"]: (r["is_curated"], r["curated_at"])
            for r in records
        }
