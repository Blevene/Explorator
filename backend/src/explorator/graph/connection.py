"""Neo4j driver connection management."""

import asyncio

from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.config import settings

_driver: AsyncDriver | None = None
_lock = asyncio.Lock()


async def get_driver() -> AsyncDriver:
    """Get or create the Neo4j async driver singleton (thread-safe)."""
    global _driver
    if _driver is None:
        async with _lock:
            if _driver is None:  # Double-check after acquiring lock
                _driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
    return _driver


async def close_driver() -> None:
    """Close the Neo4j driver."""
    global _driver
    async with _lock:
        if _driver is not None:
            await _driver.close()
            _driver = None
