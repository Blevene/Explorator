"""Security hardening: path containment, host/origin guard, request caps.

Memory mode (`client_memory`), so no Neo4j is needed.
"""
import os

import pytest

from explorator.config import settings
from explorator.persistence.memory_store import get_memory_store


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    from explorator.api.deps import get_llm_client

    monkeypatch.setenv("LLM_MOCK", "true")
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


def _new_session(client) -> str:
    return client.post("/v1/sessions", json={"genre": "dream_pop"}).json()["session_id"]


# ── path containment ─────────────────────────────────────────────────────────


def test_download_refuses_artifact_path_outside_export_dir(client_memory, tmp_path):
    secret = tmp_path / "secret.env"
    secret.write_text("LLM_API_KEY=do-not-leak")
    get_memory_store().create(
        "RenderArtifact",
        {"id": "art_evil", "type": "render_artifact", "path": str(secret),
         "artifact_type": "json", "export_package_id": "pkg_x"},
    )
    resp = client_memory.get("/v1/exports/pkg_x/artifacts/art_evil/download")
    assert resp.status_code == 404
    assert b"do-not-leak" not in resp.content


def test_delete_session_cannot_escape_export_dir(client_memory, tmp_path, monkeypatch):
    export_root = tmp_path / "exports"
    export_root.mkdir()
    keep = tmp_path / "keep.txt"
    keep.write_text("x")
    monkeypatch.setattr(settings, "export_dir", str(export_root))
    get_memory_store().create("Session", {"id": "..", "type": "session", "metadata": {}})

    client_memory.delete("/v1/sessions/%2E%2E")

    assert keep.exists()
    assert export_root.exists()


def test_delete_session_still_removes_its_exports(client_memory, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "export_dir", str(tmp_path))
    session_id = _new_session(client_memory)
    (tmp_path / session_id).mkdir()
    (tmp_path / session_id / "a.mid").write_bytes(b"x")

    assert client_memory.delete(f"/v1/sessions/{session_id}").status_code == 204
    assert not (tmp_path / session_id).exists()


# ── host / origin guard ──────────────────────────────────────────────────────


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8080", "192.168.1.50:8080",
                                  "[::1]:8000", "testserver"])
def test_host_guard_admits_local_hosts_and_ip_literals(client_memory, host):
    resp = client_memory.get("/v1/capabilities", headers={"host": host})
    assert resp.status_code == 200


def test_host_guard_rejects_unknown_hostnames(client_memory):
    # DNS rebinding: the attacker's domain resolves to 127.0.0.1.
    resp = client_memory.get("/v1/capabilities", headers={"host": "rebind.attacker.example"})
    assert resp.status_code == 400


def test_allowed_hosts_wildcard_disables_host_guard(client_memory, monkeypatch):
    monkeypatch.setattr(settings, "allowed_hosts", "*")
    resp = client_memory.get("/v1/capabilities", headers={"host": "anything.example"})
    assert resp.status_code == 200


def test_cross_site_post_is_rejected(client_memory):
    resp = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop"},
        headers={"origin": "https://evil.example"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("headers", [
    {},  # curl / server-to-server: no Origin
    {"origin": "http://testserver"},  # same origin
    # Vite proxy (changeOrigin + xfwd): Host is rewritten, X-Forwarded-Host keeps the UI's
    {"origin": "http://192.168.1.50:5173", "x-forwarded-host": "192.168.1.50:5173"},
])
def test_same_origin_and_originless_posts_pass(client_memory, headers):
    resp = client_memory.post("/v1/sessions", json={"genre": "dream_pop"}, headers=headers)
    assert resp.status_code == 201


def test_no_cors_headers_for_foreign_origins(client_memory):
    resp = client_memory.options(
        "/v1/sessions",
        headers={"origin": "https://evil.example", "access-control-request-method": "DELETE"},
    )
    assert "access-control-allow-origin" not in resp.headers


# ── request caps ─────────────────────────────────────────────────────────────


def test_realization_rejects_oversized_id_list(client_memory):
    session_id = _new_session(client_memory)
    resp = client_memory.post(
        f"/v1/sessions/{session_id}/realization-rounds",
        json={"progression_candidate_ids": [f"c{i}" for i in range(13)]},
    )
    assert resp.status_code == 422


def test_mutation_rejects_oversized_id_list(client_memory):
    session_id = _new_session(client_memory)
    resp = client_memory.post(
        f"/v1/sessions/{session_id}/mutate",
        json={"candidate_ids": [f"c{i}" for i in range(13)]},
    )
    assert resp.status_code == 422


def test_id_lists_are_deduplicated():
    from explorator.api.routes.mutations import TriggerMutationRequest
    from explorator.api.routes.realization_rounds import TriggerRealizationRequest

    req = TriggerRealizationRequest(progression_candidate_ids=["a"] * 50 + ["b"])
    assert req.progression_candidate_ids == ["a", "b"]
    assert TriggerMutationRequest(candidate_ids=["a", "a"]).candidate_ids == ["a"]


@pytest.mark.parametrize(("path", "body"), [
    ("/v1/sessions", {"genre": "dream_pop", "prompt": "x" * 5000}),
    ("/v1/genres/research", {"genre_name": "trip_hop", "reference_artists": ["a"] * 50}),
])
def test_free_text_inputs_are_bounded(client_memory, path, body):
    assert client_memory.post(path, json=body).status_code == 422


def test_export_dir_not_created_outside_root(tmp_path):
    from explorator.api.safe_paths import resolve_under

    with pytest.raises(ValueError):
        resolve_under(str(tmp_path), "..", "pkg")
    assert os.path.dirname(resolve_under(str(tmp_path), "sess_1", "pkg")) == os.path.join(
        os.path.realpath(tmp_path), "sess_1"
    )


# ── export paths portable across runtimes ────────────────────────────────────


def _seed_export(store) -> None:
    store.create("Session", {"id": "sess_port", "type": "session", "metadata": {}})
    store.create("VoicingPlan", {
        "id": "vp_p", "type": "voicing_plan", "status": "active",
        "voicing_events": [{"bar": 1, "beat": 1.0, "duration_beats": 4.0,
                            "pitches": ["C4", "E4", "G4"], "chord_symbol": "C"}],
    })
    store.create("BassLine", {
        "id": "bl_p", "type": "bass_line", "status": "active",
        "note_events": [{"bar": 1, "beat": 1.0, "duration_beats": 4.0, "pitch": "C2"}],
    })
    store.create("ArrangementCandidate", {
        "id": "arr_p", "type": "arrangement_candidate", "status": "active",
        "session_id": "sess_port", "progression_candidate_id": "prog_x",
        "voicing_plan_id": "vp_p", "bass_line_id": "bl_p", "rationale": "seeded",
        "metadata": {"label": "arr"},
    })


def test_export_paths_are_stored_relative_to_export_dir(client_memory, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "export_dir", str(tmp_path / "a"))
    store = get_memory_store()
    _seed_export(store)
    body = client_memory.post(
        "/v1/sessions/sess_port/export",
        json={"arrangement_candidate_ids": ["arr_p"], "formats": ["midi_combined"]},
    ).json()
    art_id = body["artifacts"][0]["id"]
    stored = store.get("RenderArtifact", art_id)["path"]
    assert not os.path.isabs(stored)
    assert stored.startswith("sess_port" + os.sep)

    # The same export dir mounted elsewhere (Docker /app/exports vs native) still serves it.
    os.rename(tmp_path / "a", tmp_path / "b")
    monkeypatch.setattr(settings, "export_dir", str(tmp_path / "b"))
    resp = client_memory.get(f"/v1/exports/{body['id']}/artifacts/{art_id}/download")
    assert resp.status_code == 200 and resp.content


def test_download_accepts_legacy_cwd_relative_paths(client_memory, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "export_dir", "exports")
    (tmp_path / "exports" / "sess_old" / "pkg").mkdir(parents=True)
    (tmp_path / "exports" / "sess_old" / "pkg" / "a.mid").write_bytes(b"MThd")
    get_memory_store().create("RenderArtifact", {
        "id": "art_old", "type": "render_artifact", "artifact_type": "midi_combined",
        "path": os.path.join("exports", "sess_old", "pkg", "a.mid"),
    })
    resp = client_memory.get("/v1/exports/pkg/artifacts/art_old/download")
    assert resp.status_code == 200 and resp.content == b"MThd"


def test_forwarded_host_must_itself_be_allowed(client_memory):
    resp = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop"},
        headers={"origin": "http://evil.example", "x-forwarded-host": "evil.example"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("headers", [{"host": "[::1"}, {"origin": "http://["}])
def test_malformed_host_or_origin_is_rejected_not_500(client_memory, headers):
    resp = client_memory.post("/v1/sessions", json={"genre": "dream_pop"}, headers=headers)
    assert resp.status_code in (400, 403)


def test_feedback_text_is_bounded(client_memory):
    session_id = _new_session(client_memory)
    resp = client_memory.post(
        f"/v1/sessions/{session_id}/feedback", json={"candidate_id": "c1", "content": "x" * 5000}
    )
    assert resp.status_code == 422
