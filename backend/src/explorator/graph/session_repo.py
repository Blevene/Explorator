"""Session-specific Neo4j repository."""

import json
from typing import Any

from explorator.graph.repository import BaseRepository


class SessionRepository(BaseRepository):
    """CRUD operations for Session nodes."""

    label = "Session"

    async def set_final_selection(
        self, session_id: str, payload: dict[str, Any]
    ) -> None:
        """Store the round's final selection on the Session node.

        Persisted as a JSON string under `final_selection` (matching the prior
        direct-Cypher write) so the UI can re-fetch the selection on page load.
        """
        fs_json = json.dumps(payload)
        query = "MATCH (s:Session {id: $id}) SET s.final_selection = $fs"
        async with self.driver.session() as session:
            await session.run(query, id=session_id, fs=fs_json)

    async def update_metadata(
        self, session_id: str, metadata: dict[str, Any]
    ) -> None:
        """Overwrite the Session node's metadata.

        Stored as a JSON string (matching how `create` serialises nested dicts),
        so reads via `get_by_id` deserialise it back to a dict.
        """
        md_json = json.dumps(metadata)
        query = "MATCH (s:Session {id: $id}) SET s.metadata = $md"
        async with self.driver.session() as session:
            await session.run(query, id=session_id, md=md_json)

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
