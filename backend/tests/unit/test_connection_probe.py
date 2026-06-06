import explorator.graph.connection as conn


async def test_probe_returns_none_when_unreachable(monkeypatch):
    """probe_driver returns None (not raise) when connectivity check fails."""
    class _Boom:
        async def verify_connectivity(self):
            raise OSError("refused")
        async def close(self):
            pass

    monkeypatch.setattr(
        conn.AsyncGraphDatabase, "driver", lambda *a, **k: _Boom()
    )
    await conn.close_driver()
    result = await conn.probe_driver(timeout=0.1)
    assert result is None
    assert conn.neo4j_available() is False
    assert await conn.get_optional_driver() is None


async def test_probe_returns_driver_when_reachable(monkeypatch):
    class _Ok:
        async def verify_connectivity(self):
            return None
        async def close(self):
            pass

    monkeypatch.setattr(
        conn.AsyncGraphDatabase, "driver", lambda *a, **k: _Ok()
    )
    await conn.close_driver()
    result = await conn.probe_driver(timeout=0.1)
    assert result is not None
    assert conn.neo4j_available() is True
    assert await conn.get_optional_driver() is result
    await conn.close_driver()
    assert conn.neo4j_available() is False
