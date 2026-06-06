from explorator.persistence.memory_store import MemoryStore, get_memory_store


def test_create_get_roundtrip():
    s = MemoryStore()
    s.create("Session", {"id": "a", "genre": "jazz"})
    assert s.get("Session", "a") == {"id": "a", "genre": "jazz"}
    assert s.get("Session", "missing") is None


def test_get_returns_copy_not_reference():
    s = MemoryStore()
    s.create("Session", {"id": "a", "n": 1})
    got = s.get("Session", "a")
    got["n"] = 999
    assert s.get("Session", "a")["n"] == 1  # store not mutated


def test_query_by_property_and_all():
    s = MemoryStore()
    s.create("Cand", {"id": "1", "session_id": "S"})
    s.create("Cand", {"id": "2", "session_id": "S"})
    s.create("Cand", {"id": "3", "session_id": "T"})
    assert {r["id"] for r in s.query("Cand", "session_id", "S")} == {"1", "2"}
    assert len(s.all("Cand")) == 3


def test_update_and_upsert():
    s = MemoryStore()
    s.create("X", {"id": "1", "status": "new"})
    s.update("X", "1", status="done")
    assert s.get("X", "1")["status"] == "done"
    s.upsert("X", key=("scid", "ptype"),
             props={"id": "9", "scid": "c", "ptype": "p", "v": 1})
    s.upsert("X", key=("scid", "ptype"),
             props={"id": "ignored", "scid": "c", "ptype": "p", "v": 2},
             immutable_on_match=("id",))
    rows = [r for r in s.all("X") if r.get("scid") == "c"]
    assert len(rows) == 1 and rows[0]["id"] == "9" and rows[0]["v"] == 2


def test_singleton_shared():
    get_memory_store().clear()
    get_memory_store().create("S", {"id": "z"})
    assert get_memory_store().get("S", "z") is not None
    get_memory_store().clear()
    assert get_memory_store().get("S", "z") is None
