"""Shared test fixtures.

The pytest suite requires an isolated Neo4j instance — every test's teardown
runs `MATCH (n) DETACH DELETE n`, so hitting the dev database clears it. The
`neo4j-test` service in docker-compose.yml binds to port 7689 for exactly
this; defaults below point there.

Override with `NEO4J_TEST_URI` / `NEO4J_TEST_PASSWORD` if you run the test
Neo4j elsewhere (CI, remote box). Do NOT reuse the app's `NEO4J_URI` env —
that's the dev/prod database and the teardown will wipe it.
"""

import os

# Redirect the *app's* Neo4j config at the isolated test container, so any
# code path that goes through `explorator.config.settings` (e.g. `create_app`
# inside a FastAPI TestClient) writes to the test DB instead of dev.
# Must run before any `explorator.*` import — pydantic-settings reads env
# vars when the Settings singleton is instantiated at module load.
os.environ.setdefault("NEO4J_TEST_URI", "bolt://localhost:7689")
os.environ.setdefault("NEO4J_TEST_PASSWORD", "explorator_test")
os.environ["NEO4J_URI"] = os.environ["NEO4J_TEST_URI"]
os.environ["NEO4J_PASSWORD"] = os.environ["NEO4J_TEST_PASSWORD"]

from collections.abc import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from neo4j import AsyncDriver, AsyncGraphDatabase  # noqa: E402

from explorator.graph.schema import init_schema  # noqa: E402


def _test_neo4j_uri() -> str:
    return os.environ["NEO4J_TEST_URI"]


def _test_neo4j_auth() -> tuple[str, str]:
    return (
        os.getenv("NEO4J_TEST_USER", "neo4j"),
        os.environ["NEO4J_TEST_PASSWORD"],
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def neo4j_driver() -> AsyncGenerator[AsyncDriver, None]:
    """Connect to the isolated test Neo4j (session-scoped for efficiency).

    Also registers the driver as the connection module's active driver so
    ``get_optional_driver()`` (used by the API deps/routes) returns it in tests
    that build the app via ``create_app()`` without running its lifespan. This
    mirrors what ``probe_driver()`` does at startup in production.
    """
    import explorator.graph.connection as conn

    driver = AsyncGraphDatabase.driver(_test_neo4j_uri(), auth=_test_neo4j_auth())
    await init_schema(driver)
    conn._driver = driver
    conn._available = True
    yield driver
    conn._driver = None
    conn._available = False
    await driver.close()


@pytest_asyncio.fixture(autouse=True)
async def clean_db(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:
    """Clean all nodes between tests (function-scoped for isolation)."""
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
