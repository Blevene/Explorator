"""Memory-mode (Neo4j-absent) API endpoint behaviour.

Uses the `client_memory` fixture (forces `persistence_mode == "memory"` by
patching `probe_driver`→None before lifespan). Contract: generation-path reads
work off the in-memory store; learning/recall endpoints return empty/neutral with
200 — never 500. Curation degrades to 409.

`client_memory` is a synchronous `TestClient`, so these tests are sync.
"""
import pytest

from explorator.persistence.memory_store import get_memory_store


@pytest.fixture(autouse=True)
def _mock_gemini(monkeypatch):
    """Use the fake Gemini client so routes with a `gemini` dep can resolve it.

    `get_gemini_client` is lru_cached, so clear it after setting the env var.
    """
    from explorator.api.deps import get_gemini_client

    monkeypatch.setenv("GEMINI_MOCK", "true")
    get_gemini_client.cache_clear()
    yield
    get_gemini_client.cache_clear()


@pytest.fixture(autouse=True)
def _clean_store():
    """Isolate the process-singleton MemoryStore between tests."""
    get_memory_store().clear()
    yield
    get_memory_store().clear()


def test_create_then_list_sessions(client_memory):
    resp = client_memory.post(
        "/v1/sessions",
        json={"genre": "dream_pop", "mode": "full_exploration", "prompt": "dreamy pad"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]
    assert session_id

    listed = client_memory.get("/v1/sessions")
    assert listed.status_code == 200
    ids = [s["session_id"] for s in listed.json()["items"]]
    assert session_id in ids


def test_get_session_roundtrip(client_memory):
    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "lofi"}
    ).json()["session_id"]
    got = client_memory.get(f"/v1/sessions/{session_id}")
    assert got.status_code == 200
    assert got.json()["prompt"] == "lofi"
    assert got.json()["genre"] == "dream_pop"


def test_delete_session_memory_mode(client_memory):
    """DELETE actually removes the session from the in-memory store."""
    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "lofi"}
    ).json()["session_id"]
    assert client_memory.get(f"/v1/sessions/{session_id}").status_code == 200

    resp = client_memory.delete(f"/v1/sessions/{session_id}")
    assert resp.status_code == 204

    # After delete the session is gone (was previously a no-op returning 200).
    assert client_memory.get(f"/v1/sessions/{session_id}").status_code == 404


def test_list_genres_from_yaml(client_memory):
    """Genres are served from YAML even without a database."""
    resp = client_memory.get("/v1/genres")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert all("genre" in g for g in items)


def test_get_genre_detail_from_yaml(client_memory):
    genres = client_memory.get("/v1/genres").json()["items"]
    genre = genres[0]["genre"]
    detail = client_memory.get(f"/v1/genres/{genre}")
    assert detail.status_code == 200
    assert detail.json().get("genre") == genre


def test_list_patterns_empty_200(client_memory):
    resp = client_memory.get("/v1/patterns")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_feedback_is_noop_200(client_memory):
    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "test"}
    ).json()["session_id"]
    resp = client_memory.post(
        f"/v1/sessions/{session_id}/feedback",
        json={"candidate_id": "c1", "content": "more jazzy"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Neutral, no learning: returns canonical default weights.
    assert body["satisfaction"] == "neutral"
    assert body["adjusted_weights"]  # non-empty default weights


def test_feedback_unknown_session_404(client_memory):
    resp = client_memory.post(
        "/v1/sessions/sess_missing/feedback",
        json={"candidate_id": "c1", "content": "x"},
    )
    assert resp.status_code == 404


def test_provenance_empty_200(client_memory):
    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "x"}
    ).json()["session_id"]
    resp = client_memory.get(f"/v1/sessions/{session_id}/provenance")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


def test_genre_research_drafts_empty_200(client_memory):
    resp = client_memory.get("/v1/genres/drafts")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_explanation_get_404_when_absent(client_memory):
    """No cached explanation in memory mode → 404 (existing semantic), not 500."""
    resp = client_memory.get("/v1/candidates/c_missing/explanation")
    assert resp.status_code == 404


def test_comparison_record_noop_201(client_memory):
    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "x"}
    ).json()["session_id"]
    resp = client_memory.post(
        f"/v1/sessions/{session_id}/comparisons",
        json={"candidate_ids": ["a", "b"]},
    )
    assert resp.status_code == 201
    assert resp.json()["comparison_id"].startswith("cv_")


def test_round_persists_in_session_genre_switch(client_memory, monkeypatch):
    """Triggering a round with a new genre updates the stored session metadata.

    The graph is stubbed to a no-op so the test exercises only the resolution +
    persistence seam in the round handler, not the full generation pipeline.
    """
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value={})
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "dreamy"}
    ).json()["session_id"]

    # Drain the SSE stream so the background task runs to completion.
    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={"genre": "synthwave"}
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    got = client_memory.get(f"/v1/sessions/{session_id}")
    assert got.json()["genre"] == "synthwave"
    # Mood/prompt is untouched when the round request omits a prompt.
    assert got.json()["prompt"] == "dreamy"


def test_round_threads_session_key_and_mode(client_memory, monkeypatch):
    """A session created with key='A', musical_mode='dorian' must thread those
    into the exploration graph's initial_state as key_center / mode (the
    generator's param names). Without the fix key_center stays None and the
    generator defaults to C major."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds

    captured: dict[str, object] = {}

    async def _capture(initial_state, *a, **k):
        captured["key_center"] = initial_state.get("key_center")
        captured["mode"] = initial_state.get("mode")
        return {}

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=_capture)
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions",
        json={"genre": "dream_pop", "prompt": "modal", "key": "A", "musical_mode": "dorian"},
    ).json()["session_id"]

    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={}
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    assert captured["key_center"] == "A"
    assert captured["mode"] == "dorian"


def test_round_persists_in_session_key_mode_switch(client_memory, monkeypatch):
    """Switching key/mode in a round request persists to session metadata and
    reaches the graph."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds

    captured: dict[str, object] = {}

    async def _capture(initial_state, *a, **k):
        captured["key_center"] = initial_state.get("key_center")
        captured["mode"] = initial_state.get("mode")
        return {}

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=_capture)
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "x"}
    ).json()["session_id"]

    with client_memory.stream(
        "POST",
        f"/v1/sessions/{session_id}/rounds",
        json={"key": "Eb", "musical_mode": "lydian"},
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    assert captured["key_center"] == "Eb"
    assert captured["mode"] == "lydian"

    got = client_memory.get(f"/v1/sessions/{session_id}")
    assert got.json()["key"] == "Eb"
    assert got.json()["musical_mode"] == "lydian"


def test_round_without_genre_keeps_stored_genre(client_memory, monkeypatch):
    """A round triggered without a genre leaves the stored genre intact."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(return_value={})
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "cinematic", "prompt": "lush"}
    ).json()["session_id"]

    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={}
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    got = client_memory.get(f"/v1/sessions/{session_id}")
    assert got.json()["genre"] == "cinematic"


def test_mutation_threads_session_genre(client_memory, monkeypatch):
    """The mutation path threads the session's genre to BOTH seams.

    A session created with genre "synthwave" must (1) call the harmony mutator
    with genre="synthwave" and (2) invoke the re-realization subgraph with
    initial_state["genre"]="synthwave". In memory mode neither is gated on
    Neo4j, and without the fix the mutator gets "" and load_context defaults to
    "dream_pop". The mutator and realization subgraph are stubbed so the test
    exercises only the genre-resolution seam.
    """
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.mutations as mutations
    from explorator.domain.harmony.mutator import MutationResponse

    captured: dict[str, object] = {}

    # Stub the mutator to capture the genre it is called with and return a
    # deterministic mutated progression.
    class _FakeMutator:
        def __init__(self, _gemini):
            pass

        async def mutate_harmonic(self, *, chord_symbols, genre, scores, guidance):
            captured["mutator_genre"] = genre
            return MutationResponse(
                mutated_chord_symbols=["Dmaj7"],
                mutations=[],
            )

    monkeypatch.setattr(mutations, "HarmonyMutator", _FakeMutator)

    # Stub the realization subgraph to capture the initial state's genre.
    fake_graph = MagicMock()

    async def _capture_ainvoke(initial_state, *a, **k):
        captured["realization_genre"] = initial_state.get("genre")
        return {}

    fake_graph.ainvoke = AsyncMock(side_effect=_capture_ainvoke)
    monkeypatch.setattr(
        mutations, "build_realization_subgraph", lambda *a, **k: fake_graph
    )

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "synthwave", "prompt": "moody"}
    ).json()["session_id"]

    # Seed a candidate the mutation can operate on.
    store = get_memory_store()
    store.create(
        "ProgressionCandidate",
        {
            "id": "prog_mut1",
            "type": "progression_candidate",
            "status": "candidate",
            "session_id": session_id,
            "key_center": "C",
            "mode": "major",
            "rationale": "seeded",
            "chord_events": [
                {"bar": 1, "beat": 1.0, "duration_beats": 4.0, "symbol": "Cmaj7"},
            ],
            "chord_symbols": ["Cmaj7"],
            "metadata": {},
        },
    )

    with client_memory.stream(
        "POST",
        f"/v1/sessions/{session_id}/mutate",
        json={"candidate_ids": ["prog_mut1"]},
    ) as resp:
        assert resp.status_code == 200
        for _ in resp.iter_lines():
            pass

    assert captured.get("mutator_genre") == "synthwave"
    assert captured.get("realization_genre") == "synthwave"


def test_harvest_reports_zero_in_memory_mode(client_memory):
    """Harvest is an honest no-op in memory mode (no durable pattern library).

    Even with a finalist arrangement seeded, the report must show
    upserted_count=0 / empty ids — previously it fabricated a positive count via
    the Null repo's silent no-op upsert.
    """
    store = get_memory_store()
    store.create("Session", {"id": "sess_h", "type": "session", "status": "active"})
    store.create(
        "ArrangementCandidate",
        {
            "id": "arr_h1",
            "type": "arrangement_candidate",
            "status": "active",
            "session_id": "sess_h",
            "progression_candidate_id": "prog_h1",
            "genre": "dream_pop",
            "weighted_total": 0.9,
            "metadata": {"role": "best_overall", "label": "arr"},
        },
    )

    resp = client_memory.post("/v1/sessions/sess_h/finalists/harvest")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["upserted_count"] == 0
    assert body["upserted_pattern_ids"] == []


def test_curation_409_in_memory_mode(client_memory):
    resp = client_memory.post(
        "/v1/arrangements/arr_any/curation", json={"curated": True}
    )
    assert resp.status_code == 409


def test_seeded_candidate_read(client_memory):
    """A manually-seeded in-memory progression candidate reads back over the API."""
    store = get_memory_store()
    store.create(
        "ProgressionCandidate",
        {
            "id": "prog_seed1",
            "type": "progression_candidate",
            "status": "candidate",
            "session_id": "sess_seed",
            "key_center": "C",
            "mode": "major",
            "rationale": "seeded",
            "chord_events": [
                {"bar": 1, "beat": 1.0, "duration_beats": 4.0, "symbol": "Cmaj7"},
            ],
            "intent_tags": ["warm"],
            "metadata": {},
        },
    )

    listed = client_memory.get("/v1/sessions/sess_seed/candidates")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(c["candidate_id"] == "prog_seed1" for c in items)

    detail = client_memory.get("/v1/candidates/prog_seed1")
    assert detail.status_code == 200
    assert detail.json()["chord_symbols"] == ["Cmaj7"]


def test_seeded_arrangement_export_succeeds(client_memory, tmp_path, monkeypatch):
    """Export of an in-memory arrangement renders artifacts and returns 200."""
    from explorator.config import settings

    monkeypatch.setattr(settings, "export_dir", str(tmp_path))
    store = get_memory_store()
    store.create(
        "Session",
        {"id": "sess_exp", "type": "session", "status": "active"},
    )
    store.create(
        "VoicingPlan",
        {
            "id": "vp1",
            "type": "voicing_plan",
            "status": "active",
            "voicing_events": [
                {
                    "bar": 1,
                    "beat": 1.0,
                    "duration_beats": 4.0,
                    "chord_symbol": "Cmaj7",
                    "pitches": ["C4", "E4", "G4", "B4"],
                },
            ],
        },
    )
    store.create(
        "BassLine",
        {
            "id": "bl1",
            "type": "bass_line",
            "status": "active",
            "note_events": [
                {"bar": 1, "beat": 1.0, "duration_beats": 4.0, "pitch": "C2"},
            ],
        },
    )
    store.create(
        "ArrangementCandidate",
        {
            "id": "arr_exp1",
            "type": "arrangement_candidate",
            "status": "active",
            "session_id": "sess_exp",
            "progression_candidate_id": "prog_x",
            "voicing_plan_id": "vp1",
            "bass_line_id": "bl1",
            "rationale": "seeded",
            "metadata": {"label": "arr"},
        },
    )

    resp = client_memory.post(
        "/v1/sessions/sess_exp/export",
        json={"arrangement_candidate_ids": ["arr_exp1"], "formats": ["midi_combined"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["artifact_count"] >= 1

    # End-to-end: the export package is persisted to the in-memory store, so
    # list + download both resolve (previously a silent dead-end via Null repos).
    package_id = body["id"]
    artifact_id = body["artifacts"][0]["id"]

    listed = client_memory.get("/v1/sessions/sess_exp/exports")
    assert listed.status_code == 200
    assert any(p["id"] == package_id for p in listed.json())

    download = client_memory.get(
        f"/v1/exports/{package_id}/artifacts/{artifact_id}/download"
    )
    assert download.status_code == 200
    assert download.content  # the rendered MIDI bytes
