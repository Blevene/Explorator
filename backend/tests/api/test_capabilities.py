async def test_capabilities_shape(client):
    resp = await client.get("/v1/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["persistence_mode"] in ("neo4j", "memory")
    feats = body["features"]
    for key in (
        "durable_persistence", "pattern_library", "feedback_learning",
        "session_history", "lineage", "genre_research", "curation",
    ):
        assert key in feats
        assert isinstance(feats[key], bool)


def test_capabilities_all_false_in_memory_mode(client_memory):
    body = client_memory.get("/v1/capabilities").json()
    assert body["persistence_mode"] == "memory"
    assert all(v is False for v in body["features"].values())
