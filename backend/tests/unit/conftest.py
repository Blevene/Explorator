"""Unit test conftest — overrides Neo4j fixtures so no live DB is needed."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest_asyncio
from neo4j import AsyncDriver


@pytest_asyncio.fixture(scope="session")
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:  # type: ignore[override]
    """Stub driver — unit tests do not need a live Neo4j connection."""
    yield AsyncMock(spec=AsyncDriver)  # type: ignore[misc]


@pytest_asyncio.fixture(autouse=True)
async def clean_db(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:  # type: ignore[override]
    """No-op for unit tests."""
    yield
