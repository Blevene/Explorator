"""Genre/style Neo4j repository — upsert genre profiles, rules, grammars."""

import json
from typing import Any

from neo4j import AsyncDriver


def _flatten_for_neo4j(data: dict[str, Any]) -> dict[str, Any]:
    """Convert nested dicts/lists-of-dicts to JSON strings for Neo4j storage."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) or (
            isinstance(value, list) and value and isinstance(value[0], dict)
        ):
            result[key] = json.dumps(value)
        else:
            result[key] = value
    return result


class StyleRepository:
    """CRUD for genre-related nodes."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def upsert_genre_profile(self, genre_id: str, data: dict[str, Any]) -> None:
        """Create or update a GenreProfile node."""
        query = """
            MERGE (n:GenreProfile {id: $id})
            SET n += $props
        """
        async with self.driver.session() as session:
            await session.run(query, id=genre_id, props=_flatten_for_neo4j(data))

    async def upsert_genre_rule(
        self, rule_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update a GenreRule and link to GenreProfile."""
        query = """
            MERGE (r:GenreRule:Rule {id: $rule_id})
            SET r += $props
            WITH r
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:HAS_RULE]->(r)
        """
        flat = _flatten_for_neo4j(data)
        async with self.driver.session() as session:
            await session.run(query, rule_id=rule_id, genre_id=genre_id, props=flat)

    async def upsert_anti_pattern(
        self, ap_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update an AntiPattern and link to GenreProfile."""
        query = """
            MERGE (a:AntiPattern:Rule {id: $ap_id})
            SET a += $props
            WITH a
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:HAS_ANTI_PATTERN]->(a)
        """
        flat = _flatten_for_neo4j(data)
        async with self.driver.session() as session:
            await session.run(query, ap_id=ap_id, genre_id=genre_id, props=flat)

    async def upsert_harmonic_grammar(
        self, grammar_id: str, genre_id: str, data: dict[str, Any]
    ) -> None:
        """Create or update a HarmonicGrammar and link to GenreProfile."""
        query = """
            MERGE (h:HarmonicGrammar {id: $grammar_id})
            SET h += $props
            WITH h
            MATCH (g:GenreProfile {id: $genre_id})
            MERGE (g)-[:USES_GRAMMAR]->(h)
        """
        flat = _flatten_for_neo4j(data)
        async with self.driver.session() as session:
            await session.run(query, grammar_id=grammar_id, genre_id=genre_id, props=flat)

    async def list_genre_profiles(self) -> list[dict[str, Any]]:
        """List all genre profiles."""
        query = "MATCH (n:GenreProfile) RETURN properties(n) AS props ORDER BY n.genre"
        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [dict(r["props"]) for r in records]

    async def get_genre_profile(self, genre: str) -> dict[str, Any] | None:
        """Get a genre profile by genre name."""
        query = "MATCH (n:GenreProfile {genre: $genre}) RETURN properties(n) AS props"
        async with self.driver.session() as session:
            result = await session.run(query, genre=genre)
            record = await result.single()
            if record is None:
                return None
            return dict(record["props"])
