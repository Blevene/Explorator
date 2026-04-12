"""Neo4j repository for CandidateExplanation entities."""

from typing import Any

from explorator.graph.repository import BaseRepository


class CandidateExplanationRepo(BaseRepository):
    """CRUD operations for CandidateExplanation nodes."""

    label = "CandidateExplanation"

    async def get_by_candidate_id(self, candidate_id: str) -> dict[str, Any] | None:
        """Fetch a cached explanation for a given candidate."""
        results = await self.query_by_property("candidate_id", candidate_id)
        return results[0] if results else None
