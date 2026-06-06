"""Neo4j repository for CreativeBrief nodes."""

from typing import Any

from explorator.graph.repository import BaseRepository


class CreativeBriefRepo(BaseRepository):
    """CRUD for CreativeBrief nodes, keyed by session."""

    label = "CreativeBrief"

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        results = await self.query_by_property("session_id", session_id)
        return results[0] if results else None
