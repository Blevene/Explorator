"""Shared fixtures for API tests."""
from collections.abc import Iterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

import explorator.graph.connection as conn
from explorator.api.app import create_app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


@pytest.fixture
def client_memory(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """API client forced into memory mode.

    Patches the connection module BEFORE create_app() runs its lifespan, so the
    probe never reaches Neo4j and persistence_mode resolves to "memory". The
    lifespan imports probe_driver from the connection module at call time, so
    patching the module attribute takes effect.
    """

    async def _no_driver(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(conn, "probe_driver", _no_driver)
    monkeypatch.setattr(conn, "neo4j_available", lambda: False)
    # A prior Neo4j-mode test may have left a live driver in the module globals
    # that was opened on a different event loop. Memory-mode lifespan calls
    # close_driver() on shutdown; clearing the globals (the probe never creates
    # one) makes that close a no-op so we don't close a cross-loop driver.
    monkeypatch.setattr(conn, "_driver", None)
    monkeypatch.setattr(conn, "_available", False)

    with TestClient(create_app()) as c:  # context manager runs lifespan
        yield c
