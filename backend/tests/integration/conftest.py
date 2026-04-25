"""Integration test conftest — connects to Neo4j or skips if unavailable."""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest_asyncio
from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.graph.schema import init_schema


def _neo4j_uri() -> str:
    # Point at the isolated test Neo4j — reusing the app's NEO4J_URI would
    # let the autouse `clean_db` wipe the dev database.
    return os.getenv("NEO4J_TEST_URI", "bolt://localhost:7689")


def _neo4j_auth() -> tuple[str, str]:
    return (
        os.getenv("NEO4J_TEST_USER", "neo4j"),
        os.getenv("NEO4J_TEST_PASSWORD", "explorator_test"),
    )


_neo4j_available: bool | None = None


@pytest_asyncio.fixture(scope="session")
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:  # type: ignore[override]
    """Connect to Neo4j for integration tests, or yield a stub if unavailable.

    Tests that need a real DB should call ``pytest.importorskip`` or check
    the ``neo4j_available`` fixture themselves.  The autouse ``clean_db``
    fixture is a no-op when the real DB is absent.
    """
    global _neo4j_available
    from neo4j.exceptions import ServiceUnavailable

    drv = AsyncGraphDatabase.driver(_neo4j_uri(), auth=_neo4j_auth())
    try:
        await init_schema(drv)
        _neo4j_available = True
        yield drv
        await drv.close()
    except ServiceUnavailable:
        _neo4j_available = False
        await drv.close()
        yield AsyncMock(spec=AsyncDriver)  # type: ignore[misc]


@pytest_asyncio.fixture(autouse=True)
async def clean_db(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:  # type: ignore[override]
    """Clean all nodes between tests (no-op when Neo4j is unavailable)."""
    yield
    if _neo4j_available:
        async with neo4j_driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
