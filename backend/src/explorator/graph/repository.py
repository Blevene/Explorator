"""Base Neo4j repository with generic CRUD operations."""

import json
from datetime import UTC, datetime
from typing import Any

from neo4j import AsyncDriver
from pydantic import BaseModel


def _neo4j_safe(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce values to Neo4j-compatible primitives.

    Neo4j node properties must be primitives or homogeneous arrays of primitives.
    Nested dicts and mixed-type containers are serialised to JSON strings.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = json.dumps(value)
        elif isinstance(value, list):
            # Keep lists of primitives as-is; serialise otherwise
            if all(isinstance(v, (str, int, float, bool)) for v in value):
                result[key] = value
            else:
                result[key] = json.dumps(value)
        else:
            result[key] = value
    return result


class BaseRepository:
    """Generic Neo4j node CRUD. Subclasses set `label`."""

    label: str = "Node"

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def create(self, entity: BaseModel) -> None:
        """Create a node from a Pydantic model."""
        data = _neo4j_safe(entity.model_dump(mode="json"))
        query = f"CREATE (n:{self.label} $props) SET n.id = $props.id"
        async with self.driver.session() as session:
            await session.run(query, props=data)

    async def get_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Read a node by ID."""
        query = f"MATCH (n:{self.label} {{id: $id}}) RETURN properties(n) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, id=entity_id)
            record = await result.single()
            if record is None:
                return None
            return dict(record["props"])

    async def update_status(self, entity_id: str, status: str) -> None:
        """Update a node's status."""
        query = f"""
            MATCH (n:{self.label} {{id: $id}})
            SET n.status = $status, n.updated_at = $now
        """
        async with self.driver.session() as session:
            await session.run(
                query,
                id=entity_id,
                status=status,
                now=datetime.now(UTC).isoformat(),
            )
