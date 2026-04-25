"""Neo4j CRUD for GenreResearchJob nodes."""

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


def _flatten_for_neo4j(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten complex values to JSON strings for Neo4j storage."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value)
        elif isinstance(value, datetime):
            flat[key] = value.isoformat()
        else:
            flat[key] = value
    return flat


def _unflatten_from_neo4j(props: dict[str, Any]) -> dict[str, Any]:
    """Restore JSON strings back to Python objects."""
    result = dict(props)
    for key in ("draft_yamls", "critique_trail", "reference_artists", "validation_errors"):
        if key in result and isinstance(result[key], str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                result[key] = json.loads(result[key])
    return result


class GenreResearchRepository:
    """Neo4j CRUD for GenreResearchJob."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def create_job(self, job_data: dict[str, Any]) -> None:
        """Create a new GenreResearchJob node."""
        query = """
            CREATE (j:GenreResearchJob {id: $id})
            SET j += $props
        """
        flat = _flatten_for_neo4j(job_data)
        async with self.driver.session() as session:
            await session.run(query, id=job_data["id"], props=flat)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID."""
        query = "MATCH (j:GenreResearchJob {id: $id}) RETURN properties(j) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, id=job_id)
            record = await result.single()
            if record is None:
                return None
            return _unflatten_from_neo4j(dict(record["props"]))

    async def update_job(self, job_id: str, updates: dict[str, Any]) -> None:
        """Partial update of a job node."""
        updates["updated_at"] = datetime.now(tz=UTC).isoformat()
        flat = _flatten_for_neo4j(updates)
        query = """
            MATCH (j:GenreResearchJob {id: $id})
            SET j += $props
        """
        async with self.driver.session() as session:
            await session.run(query, id=job_id, props=flat)

    async def list_pending_drafts(self) -> list[dict[str, Any]]:
        """List jobs with status=pending_review."""
        query = """
            MATCH (j:GenreResearchJob {status: 'pending_review'})
            RETURN properties(j) AS props
            ORDER BY j.created_at DESC
        """
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [_unflatten_from_neo4j(dict(r["props"])) for r in records]

    async def job_exists_for_genre(self, genre_name: str) -> bool:
        """Check if there's an in-progress job for this genre name."""
        query = """
            MATCH (j:GenreResearchJob {genre_name: $name})
            WHERE j.status IN ['researching', 'drafting', 'critiquing', 'refining', 'validating', 'pending_review']
            RETURN count(j) AS cnt
        """  # noqa: E501
        async with self.driver.session() as session:
            result = await session.run(query, name=genre_name)
            record = await result.single()
            return record is not None and record["cnt"] > 0
