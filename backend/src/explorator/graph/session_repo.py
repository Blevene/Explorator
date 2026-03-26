"""Session-specific Neo4j repository."""

from typing import Any

from explorator.graph.repository import BaseRepository


class SessionRepository(BaseRepository):
    """CRUD operations for Session nodes."""

    label = "Session"

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions ordered by creation time."""
        query = """
            MATCH (n:Session)
            RETURN properties(n) AS props
            ORDER BY n.created_at DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [dict(r["props"]) for r in records]
