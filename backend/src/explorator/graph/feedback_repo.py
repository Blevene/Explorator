"""Neo4j repositories for feedback events and objective weights."""

from typing import Any

from explorator.graph.repository import BaseRepository, _neo4j_deserialize


class FeedbackEventRepo(BaseRepository):
    """CRUD for UserFeedbackEvent nodes."""

    label = "UserFeedbackEvent"

    async def list_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """List all feedback events for a session, ordered by creation time."""
        query = """
            MATCH (n:UserFeedbackEvent {session_id: $session_id})
            RETURN properties(n) AS props
            ORDER BY n.created_at ASC
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            records = await result.data()
            return [_neo4j_deserialize(dict(r["props"])) for r in records]


class ObjectiveWeightsRepo(BaseRepository):
    """CRUD for ObjectiveWeights nodes."""

    label = "ObjectiveWeights"

    async def get_latest_for_session(self, session_id: str) -> dict[str, Any] | None:
        """Get the most recently created ObjectiveWeights for a session."""
        query = """
            MATCH (n:ObjectiveWeights)
            WHERE n.profile_name STARTS WITH $prefix
            RETURN properties(n) AS props
            ORDER BY n.created_at DESC
            LIMIT 1
        """
        async with self.driver.session() as session:
            result = await session.run(query, prefix=f"session_{session_id}")
            record = await result.single()
            if record is None:
                return None
            return _neo4j_deserialize(dict(record["props"]))
