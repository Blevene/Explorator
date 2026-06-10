from fastapi.testclient import TestClient

import explorator.graph.connection as conn
from explorator.api.app import create_app


def test_app_boots_in_memory_mode(monkeypatch):
    """With Neo4j unreachable, the app still starts and reports memory mode."""

    async def _no_driver(*a, **k):
        return None

    monkeypatch.setattr(conn, "probe_driver", _no_driver)
    monkeypatch.setattr(conn, "neo4j_available", lambda: False)
    # Clear any driver a prior Neo4j-mode test opened on another event loop so
    # the memory-mode lifespan's close_driver() is a no-op (the probe never
    # creates one here).
    monkeypatch.setattr(conn, "_driver", None)
    monkeypatch.setattr(conn, "_available", False)

    app = create_app()
    with TestClient(app) as client:  # runs lifespan; must NOT raise
        assert app.state.persistence_mode == "memory"
        resp = client.get("/v1/capabilities")
        assert resp.status_code == 200
        assert resp.json()["persistence_mode"] == "memory"
