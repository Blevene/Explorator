"""Shared test fixtures."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from neo4j import AsyncDriver, AsyncGraphDatabase

from explorator.graph.schema import init_schema


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:
    """Connect to test Neo4j instance (session-scoped for efficiency)."""
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7688",
        auth=("neo4j", "explorator_dev"),
    )
    await init_schema(driver)
    yield driver
    await driver.close()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:
    """Clean all nodes between tests (function-scoped for isolation)."""
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
