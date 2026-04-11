"""Neo4j repositories for feedback events and objective weights."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from explorator.graph.repository import BaseRepository, _neo4j_deserialize, _neo4j_safe

if TYPE_CHECKING:
    from explorator.models.base import BaseEntity


class FeedbackEventRepo(BaseRepository):
    """CRUD for UserFeedbackEvent nodes."""

    label = "UserFeedbackEvent"

    async def create_with_relationships(
        self,
        event: "BaseEntity",
        weights_id: str,
        session_id: str,
    ) -> None:
        """Create feedback event and its Neo4j relationships in a single transaction."""
        data = _neo4j_safe(event.model_dump(mode="json"))
        async with self.driver.session() as session:
            tx = await session.begin_transaction()
            try:
                # Create feedback node
                await tx.run(
                    f"CREATE (n:{self.label} $props) SET n.id = $props.id",
                    props=data,
                )
                # (UserFeedbackEvent)-[:ABOUT]->(candidate)
                await tx.run(
                    "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (c {id: $cand_id}) "
                    "CREATE (fb)-[:ABOUT]->(c)",
                    fb_id=event.id, cand_id=data.get("candidate_id", ""),
                )
                # (UserFeedbackEvent)-[:UPDATES]->(ObjectiveWeights)
                await tx.run(
                    "MATCH (fb:UserFeedbackEvent {id: $fb_id}), (ow:ObjectiveWeights {id: $ow_id}) "
                    "CREATE (fb)-[:UPDATES]->(ow)",
                    fb_id=event.id, ow_id=weights_id,
                )
                # (Session)-[:HAS_FEEDBACK]->(UserFeedbackEvent)
                await tx.run(
                    "MATCH (s:Session {id: $sess_id}), (fb:UserFeedbackEvent {id: $fb_id}) "
                    "CREATE (s)-[:HAS_FEEDBACK]->(fb)",
                    sess_id=session_id, fb_id=event.id,
                )
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

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
