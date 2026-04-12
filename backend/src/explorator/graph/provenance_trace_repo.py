"""Neo4j repository for ProvenanceTrace entities."""

import json
from typing import Any

from explorator.graph.repository import BaseRepository
from explorator.utils import utc_now


class ProvenanceTraceRepo(BaseRepository):
    """CRUD + append_events for ProvenanceTrace nodes."""

    label = "ProvenanceTrace"

    async def append_events(
        self, trace_id: str, new_events: list[dict[str, Any]]
    ) -> None:
        """Append new provenance events to an existing trace.

        Loads the current events list, extends it, and writes back.
        Raises ValueError if the trace does not exist.
        """
        existing = await self.get_by_id(trace_id)
        if existing is None:
            raise ValueError(f"ProvenanceTrace {trace_id} not found")

        current_events: list[dict[str, Any]] = existing.get("events", [])
        merged = current_events + new_events
        events_json = json.dumps(merged)

        query = f"""
            MATCH (n:{self.label} {{id: $id}})
            SET n.events = $events, n.updated_at = $now
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                id=trace_id,
                events=events_json,
                now=utc_now().isoformat(),
            )

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        """Fetch the provenance trace for a given session."""
        results = await self.query_by_property("session_id", session_id)
        return results[0] if results else None
