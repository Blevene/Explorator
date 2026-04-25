# ADR 009 — Isolated test Neo4j container with autouse cleanup

**Status:** Accepted

## Context

Many of our backend tests are integration tests that exercise the actual Cypher we ship — the upsert invariant, the LEFT-JOIN derivation, the cascade-delete, the curation transaction. Mocking the Neo4j driver doesn't catch Cypher semantic bugs (parameter binding, label scoping, `head(collect(...))` null propagation) — these only surface against a live database.

Two natural approaches:

1. **Share the dev Neo4j with the test suite.** Cheap to set up. But the autouse cleanup fixture runs `MATCH (n) DETACH DELETE n` between tests — that wipes the dev DB, destroying any session you were working on.

2. **Per-test sqlite-style ephemeral DB.** Not a thing for Neo4j. Embedded mode exists but is a separate driver and has compatibility issues.

3. **Separate Neo4j container for tests, on a separate port, with autouse cleanup.** A second container is cheap; isolation is total.

The user discovered the hard way that approach (1) can wipe the dev DB. The fix landed as PR #7 (`fix/test-db-isolation`, merged 2026-04-20).

## Decision

**Two Neo4j containers, two ports, one autouse cleanup fixture.**

`docker-compose.yml` defines:

- `neo4j` on bolt port **7688** (browser 7475) — disk-backed volume, the dev container.
- `neo4j-test` on bolt port **7689** (browser 7476) — `tmpfs` volume, ephemeral.

The pytest conftest in `backend/tests/conftest.py` redirects the app's environment **before any explorator import**:

```python
os.environ.setdefault("NEO4J_TEST_URI", "bolt://localhost:7689")
os.environ.setdefault("NEO4J_TEST_PASSWORD", "explorator_test")
os.environ["NEO4J_URI"] = os.environ["NEO4J_TEST_URI"]
os.environ["NEO4J_PASSWORD"] = os.environ["NEO4J_TEST_PASSWORD"]
```

This must run before the first `from explorator import ...` because Pydantic settings are read at module load. Any code path that goes through `explorator.config.settings` (e.g. FastAPI `TestClient` constructing an app) will land on the test DB.

The autouse `clean_db` fixture runs `MATCH (n) DETACH DELETE n` after every test:

```python
@pytest_asyncio.fixture(autouse=True)
async def clean_db(neo4j_driver):
    yield
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
```

`make test*` targets bring `neo4j-test` up automatically (`docker compose up -d --wait neo4j-test`) before invoking pytest. If you invoke pytest directly, you must `make neo4j-test-up` first or the integration tests will fail with confusing errors.

## Consequences

**Positive:**
- The dev DB is sacred — sessions you're actively working on are never wiped by tests.
- Tests are real integration tests against actual Cypher. The 100s of millisecond overhead per test is acceptable.
- The conftest pattern is reusable for any future shared resource that needs test isolation.

**Negative:**
- Two containers running locally costs ~200MB of memory baseline. Not meaningful on a dev machine.
- Tests can't run if Docker isn't running. Mitigation: the `make` targets fail with a clear error.
- The integration conftest at `backend/tests/integration/conftest.py` has a graceful fallback that mocks the driver when `neo4j-test` isn't available, so unit-only test runs don't break — but this can mask "I forgot to start the test container" if you don't notice the skip.

## Revisit if

We move to a CI environment that has its own opinion about test database setup (e.g. GitHub Actions with managed Neo4j). At that point the env-var redirection is the pivot point — set `NEO4J_TEST_URI` to the CI-provided endpoint and the rest works unchanged.

## See also

- `backend/tests/conftest.py` (env redirection + autouse cleanup)
- `backend/tests/integration/conftest.py` (graceful fallback when test DB unavailable)
- `docker-compose.yml` (the two service definitions)
- PR #7 history for the original incident that motivated this isolation
