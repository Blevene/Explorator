"""load_context genre resolution — memory mode prefers state genre.

In memory mode `persist_round` never writes `Session.genre` and no CreativeBrief
is persisted, so without state-genre preference load_context would fall through
to the "dream_pop" default. The realization trigger route sets `state["genre"]`
from session metadata; load_context must honour it.
"""

import pytest

from explorator.engine.nodes.load_context import load_context
from explorator.models.harmony import ChordEvent, ProgressionCandidate
from explorator.persistence.memory_repos import (
    MemoryCandidateRepo,
    MemorySessionRepo,
)
from explorator.persistence.memory_store import MemoryStore, get_memory_store


@pytest.fixture
def _clean_store():
    get_memory_store().clear()
    yield
    get_memory_store().clear()


async def _seed_candidate(store: MemoryStore, session_id: str) -> str:
    cand_repo = MemoryCandidateRepo(store)
    sess_repo = MemorySessionRepo(store)
    from explorator.models.session import Session

    # Session carries NO `genre` property (memory mode never sets it) and no
    # genre in metadata, so the only genre source is state.
    await sess_repo.create(
        Session(
            id=session_id,
            type="session",
            status="active",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    pc = ProgressionCandidate(
        id="pc1",
        type="progression_candidate",
        status="active",
        session_id=session_id,
        rationale="r",
        key_center="C",
        chord_events=[ChordEvent(bar=1, symbol="Cmaj7")],
        chord_symbols=["Cmaj7"],
    )
    await cand_repo.create(pc)
    return "pc1"


async def test_load_context_prefers_state_genre(_clean_store) -> None:
    """A session created with genre 'synthwave' loads synthwave's profile."""
    store = get_memory_store()
    pc_id = await _seed_candidate(store, "sess_X")

    state = {
        "session_id": "sess_X",
        "progression_candidate_ids": [pc_id],
        "genre": "synthwave",
    }

    result = await load_context(state, driver=None)

    # The profile actually loaded matches the state genre, not the default.
    assert result["genre_profile"].get("genre") == "synthwave"


async def test_load_context_defaults_without_state_genre(_clean_store) -> None:
    """Without state genre and no persisted genre, falls back to dream_pop."""
    store = get_memory_store()
    pc_id = await _seed_candidate(store, "sess_Y")

    state = {
        "session_id": "sess_Y",
        "progression_candidate_ids": [pc_id],
    }

    result = await load_context(state, driver=None)
    assert result["genre_profile"].get("genre") == "dream_pop"
