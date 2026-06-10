"""Unit tests for the in-memory generation-path repos.

These exercise the real Pydantic models so the stored/returned dict shapes are
exactly what the Neo4j repos yield after deserialization.
"""

from explorator.models.export import CandidateExplanation
from explorator.models.harmony import ChordEvent, ProgressionCandidate
from explorator.models.realization import ArrangementCandidate, BassLine, VoicingPlan
from explorator.models.session import CreativeBrief, Session
from explorator.persistence.memory_repos import (
    MemoryArrangementCandidateRepo,
    MemoryBassLineRepo,
    MemoryCandidateExplanationRepo,
    MemoryCandidateRepo,
    MemoryCreativeBriefRepo,
    MemorySessionRepo,
    MemoryVoicingPlanRepo,
)
from explorator.persistence.memory_store import MemoryStore


def _session(sid: str, created_at: str) -> Session:
    return Session(id=sid, type="session", status="active", created_at=created_at)


async def test_candidate_create_get_roundtrip() -> None:
    store = MemoryStore()
    repo = MemoryCandidateRepo(store)
    pc = ProgressionCandidate(
        id="pc1",
        type="progression_candidate",
        status="active",
        session_id="S",
        rationale="test",
        key_center="C",
        chord_events=[ChordEvent(bar=1, symbol="Cmaj7")],
        chord_symbols=["Cmaj7"],
    )
    await repo.create(pc)
    got = await repo.get_by_id("pc1")
    assert got is not None
    assert got["id"] == "pc1"
    assert got["session_id"] == "S"
    # nested list-of-dicts preserved as real dicts (not JSON strings)
    assert got["chord_events"][0]["symbol"] == "Cmaj7"
    assert got["chord_symbols"] == ["Cmaj7"]
    assert await repo.get_by_id("missing") is None


async def test_voicing_and_bass_roundtrip() -> None:
    store = MemoryStore()
    vp = VoicingPlan(id="vp1", type="voicing_plan", status="active")
    bl = BassLine(id="bl1", type="bass_line", status="active")
    await MemoryVoicingPlanRepo(store).create(vp)
    await MemoryBassLineRepo(store).create(bl)
    assert (await MemoryVoicingPlanRepo(store).get_by_id("vp1"))["id"] == "vp1"
    assert (await MemoryBassLineRepo(store).get_by_id("bl1"))["id"] == "bl1"


async def test_update_status() -> None:
    store = MemoryStore()
    repo = MemoryCandidateRepo(store)
    pc = ProgressionCandidate(
        id="pc1",
        type="progression_candidate",
        status="active",
        session_id="S",
        rationale="r",
        key_center="C",
    )
    await repo.create(pc)
    await repo.update_status("pc1", "rejected")
    got = await repo.get_by_id("pc1")
    assert got is not None
    assert got["status"] == "rejected"
    assert "updated_at" in got


async def test_query_by_property() -> None:
    store = MemoryStore()
    repo = MemoryCandidateRepo(store)
    for i, sid in enumerate(["S", "S", "T"]):
        await repo.create(
            ProgressionCandidate(
                id=f"pc{i}",
                type="progression_candidate",
                status="active",
                session_id=sid,
                rationale="r",
                key_center="C",
            )
        )
    rows = await repo.query_by_property("session_id", "S")
    assert {r["id"] for r in rows} == {"pc0", "pc1"}


async def test_session_list_ordering() -> None:
    store = MemoryStore()
    repo = MemorySessionRepo(store)
    await repo.create(_session("old", "2026-01-01T00:00:00+00:00"))
    await repo.create(_session("new", "2026-06-01T00:00:00+00:00"))
    await repo.create(_session("mid", "2026-03-01T00:00:00+00:00"))
    ids = [s["id"] for s in await repo.list_sessions()]
    assert ids == ["new", "mid", "old"]


async def test_session_update_metadata() -> None:
    store = MemoryStore()
    repo = MemorySessionRepo(store)
    session = Session(
        id="S",
        type="session",
        status="active",
        created_at="2026-01-01T00:00:00+00:00",
        metadata={"prompt": "lofi", "genre": "dream_pop"},
    )
    await repo.create(session)

    await repo.update_metadata("S", {"prompt": "lofi", "genre": "synthwave"})
    got = await repo.get_by_id("S")
    assert got is not None
    assert got["metadata"] == {"prompt": "lofi", "genre": "synthwave"}

    # No-op for an unknown session (mirrors the Neo4j MATCH semantics).
    await repo.update_metadata("missing", {"genre": "cinematic"})
    assert await repo.get_by_id("missing") is None


async def test_session_delete() -> None:
    store = MemoryStore()
    repo = MemorySessionRepo(store)
    await repo.create(_session("S", "2026-01-01T00:00:00+00:00"))
    assert await repo.get_by_id("S") is not None

    assert await repo.delete("S") is True
    assert await repo.get_by_id("S") is None

    # Deleting a missing session is a no-op returning False.
    assert await repo.delete("S") is False


async def test_candidate_explanation_cache_roundtrip() -> None:
    store = MemoryStore()
    repo = MemoryCandidateExplanationRepo(store)

    # Cold cache → None (would trigger Gemini in the route).
    assert await repo.get_by_candidate_id("arr1") is None

    expl = CandidateExplanation(
        id="ce1",
        type="candidate_explanation",
        status="active",
        session_id="S",
        candidate_id="arr1",
        summary="warm pad voicing",
        why_it_works=["smooth voice leading"],
    )
    await repo.create(expl)

    # Warm cache → returns the stored explanation (skips Gemini).
    got = await repo.get_by_candidate_id("arr1")
    assert got is not None
    assert got["id"] == "ce1"
    assert got["summary"] == "warm pad voicing"
    assert got["why_it_works"] == ["smooth voice leading"]
    # Distinct candidate id is still a miss.
    assert await repo.get_by_candidate_id("arr2") is None


async def test_arrangement_finalist_role_filtering() -> None:
    store = MemoryStore()
    repo = MemoryArrangementCandidateRepo(store)

    def _arr(aid: str, role: str | None, total: float) -> ArrangementCandidate:
        meta: dict[str, object] = {"weighted_total": total}
        if role is not None:
            meta["role"] = role
        return ArrangementCandidate(
            id=aid,
            type="arrangement_candidate",
            status="active",
            session_id="S",
            rationale="r",
            progression_candidate_id="pc1",
            metadata=meta,
        )

    await repo.create(_arr("a_low", "safest", 0.5))
    await repo.create(_arr("a_high", "best_loop", 0.9))
    await repo.create(_arr("a_norole", None, 1.0))  # excluded — no role key

    finalists = await repo.list_finalists_for_session("S")
    ids = [f["id"] for f in finalists]
    assert "a_norole" not in ids
    assert ids == ["a_high", "a_low"]  # sorted by weighted_total desc


async def test_arrangement_get_progression_candidate() -> None:
    store = MemoryStore()
    cand_repo = MemoryCandidateRepo(store)
    arr_repo = MemoryArrangementCandidateRepo(store)
    await cand_repo.create(
        ProgressionCandidate(
            id="pc1",
            type="progression_candidate",
            status="active",
            session_id="S",
            rationale="r",
            key_center="C",
        )
    )
    got = await arr_repo.get_progression_candidate("pc1")
    assert got is not None and got["id"] == "pc1"
    assert await arr_repo.get_progression_candidate("nope") is None


async def test_fetch_curation_state() -> None:
    store = MemoryStore()
    repo = MemoryArrangementCandidateRepo(store)
    state = await repo.fetch_curation_state(["a", "b"])
    assert state == {"a": (None, None), "b": (None, None)}
    assert await repo.fetch_curation_state([]) == {}


async def test_creative_brief_get_by_session_id() -> None:
    store = MemoryStore()
    repo = MemoryCreativeBriefRepo(store)
    # CreativeBrief nodes carry a session_id property when persisted (the model
    # itself has none); seed via the store to mirror that persisted shape.
    brief = CreativeBrief(
        id="cb1", type="creative_brief", status="active", genre="dream_pop"
    )
    payload = brief.model_dump(mode="json")
    payload["session_id"] = "S"
    store.create("CreativeBrief", payload)
    got = await repo.get_by_session_id("S")
    assert got is not None and got["id"] == "cb1"
    assert await repo.get_by_session_id("T") is None
