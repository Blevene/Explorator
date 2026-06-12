"""The round route emits a terminal token_usage SSE event."""

import json

import pytest


@pytest.fixture(autouse=True)
def _force_gemini_mock(monkeypatch):
    """Force mock mode for these tests.

    The round route constructs the Gemini client via DI. CI has no
    GEMINI_API_KEY, and ``genai.Client(api_key="")`` raises at construction, so a
    real client can't be built. ``FakeGeminiClient`` needs no key; the graph is
    stubbed anyway, so no real Gemini call happens. ``get_gemini_client`` is
    lru_cached, so clear it around the test to avoid leaking a real/fake client.
    """
    from explorator.api.deps import get_gemini_client

    monkeypatch.setenv("GEMINI_MOCK", "true")
    get_gemini_client.cache_clear()
    yield
    get_gemini_client.cache_clear()


def _sse_events(resp) -> list[tuple[str, dict]]:
    """Parse an SSE response body into (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    for raw in resp.iter_lines():
        line = raw if isinstance(raw, str) else raw.decode()
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event_name:
            events.append((event_name, json.loads(line.split(":", 1)[1].strip())))
            event_name = None
    return events


def test_round_emits_terminal_token_usage(client_memory, monkeypatch):
    """A round whose graph spends tokens (within the scope) emits token_usage."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds
    from explorator.adapters import usage

    async def fake_ainvoke(state, *_a, **_k):
        # Simulate an in-scope LLM call (the route opened track_usage around us).
        usage.record_tokens("gemini-pro-latest", 1000, 400)
        return {}

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "dreamy"}
    ).json()["session_id"]

    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={}
    ) as resp:
        assert resp.status_code == 200
        events = _sse_events(resp)

    token_events = [data for name, data in events if name == "token_usage"]
    assert token_events, "expected a token_usage event"
    final = token_events[-1]
    assert final["total_tokens"] == 1400
    assert final["by_model"]["pro"]["calls"] == 1
    assert final["is_estimate"] is True


def test_failed_round_still_emits_token_usage(client_memory, monkeypatch):
    """A round whose graph raises after spending tokens still reports the spend."""
    from unittest.mock import AsyncMock, MagicMock

    import explorator.api.routes.rounds as rounds
    from explorator.adapters import usage

    async def fake_ainvoke(state, *_a, **_k):
        usage.record_tokens("gemini-flash-latest", 500, 100)
        raise RuntimeError("boom")

    fake_graph = MagicMock()
    fake_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    monkeypatch.setattr(rounds, "build_exploration_graph", lambda *a, **k: fake_graph)

    session_id = client_memory.post(
        "/v1/sessions", json={"genre": "dream_pop", "prompt": "x"}
    ).json()["session_id"]

    with client_memory.stream(
        "POST", f"/v1/sessions/{session_id}/rounds", json={}
    ) as resp:
        assert resp.status_code == 200
        events = _sse_events(resp)

    names = [name for name, _ in events]
    assert "token_usage" in names, "failed round must still report spend"
    assert "round_error" in names
    token = [d for n, d in events if n == "token_usage"][-1]
    assert token["total_tokens"] == 600
