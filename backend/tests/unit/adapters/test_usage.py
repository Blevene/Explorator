"""Tests for the token-usage accumulator."""

from types import SimpleNamespace

import pytest

from explorator.adapters import usage


def test_record_tokens_is_noop_without_scope() -> None:
    # No active track_usage() scope → must not raise and must record nothing.
    usage.record_tokens("gemini-pro-latest", 100, 50)
    assert usage.current_usage() is None


def test_track_usage_aggregates_by_model_and_phase() -> None:
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 1000, 500)
        with usage.set_phase("evaluate_progressions"):
            usage.record_tokens("gemini-flash-latest", 200, 80)
            usage.record_tokens("gemini-flash-latest", 100, 40)

    totals = u.totals()
    assert totals == {"input": 1300, "output": 620, "cached": 0, "total": 1920}
    assert u.by_model["pro"].calls == 1
    assert u.by_model["flash"].calls == 2
    assert u.by_phase["generate"].model == "pro"
    assert u.by_phase["evaluate_progressions"].calls == 2


def test_record_reads_usage_metadata_none_safe() -> None:
    meta = SimpleNamespace(
        prompt_token_count=10,
        candidates_token_count=None,  # must coerce to 0
        cached_content_token_count=4,
    )
    with usage.track_usage() as u:
        usage.record("gemini-flash-latest", meta)
    assert u.totals() == {"input": 10, "output": 0, "cached": 4, "total": 10}


def test_estimated_cost_matches_pricing() -> None:
    # Defaults: pro input 1.25/M, pro output 10.0/M.
    with usage.track_usage() as u, usage.set_phase("generate"):
        usage.record_tokens("gemini-pro-latest", 1000, 500)
    # (1000/1e6*1.25) + (500/1e6*10.0) = 0.00125 + 0.005 = 0.00625
    assert round(u.estimated_cost_usd(), 6) == 0.00625


def test_changed_since_last_emit_tracks_growth() -> None:
    with usage.track_usage() as u:
        assert u.changed_since_last_emit() is False  # nothing yet
        with usage.set_phase("generate"):
            usage.record_tokens("gemini-pro-latest", 10, 5)
        assert u.changed_since_last_emit() is True
        assert u.changed_since_last_emit() is False  # no new tokens since


def test_to_event_shape() -> None:
    with usage.track_usage() as u, usage.set_phase("generate"):
        usage.record_tokens("gemini-pro-latest", 100, 40)
    event = u.to_event(round_number=2)
    assert event["round"] == 2
    assert event["total_input"] == 100
    assert event["total_output"] == 40
    assert event["total_tokens"] == 140
    assert event["by_model"]["pro"] == {"input": 100, "output": 40, "cached": 0, "calls": 1}
    assert event["by_phase"]["generate"]["model"] == "pro"
    assert event["is_estimate"] is True
    assert isinstance(event["estimated_cost_usd"], float)


async def test_adapter_records_usage_within_scope() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from pydantic import BaseModel

    from explorator.adapters.gemini import GeminiClient, ModelTier

    class _Sample(BaseModel):
        name: str
        value: int

    client = GeminiClient(api_key="test-key")
    fake_response = SimpleNamespace(
        text='{"name": "x", "value": 1}',
        usage_metadata=SimpleNamespace(
            prompt_token_count=120, candidates_token_count=30, cached_content_token_count=0
        ),
    )
    client._client.aio.models.generate_content = AsyncMock(return_value=fake_response)

    with usage.track_usage() as u, usage.set_phase("generate"):
        await client.generate_structured("p", _Sample, tier=ModelTier.PRO)

    assert u.totals() == {"input": 120, "output": 30, "cached": 0, "total": 150}
    assert u.by_phase["generate"].model == "pro"
    assert set(u.by_model) == {"pro"}


async def test_mock_client_records_synthetic_usage() -> None:
    from explorator.adapters.gemini import ModelTier
    from explorator.adapters.llm_mock import FakeLLMClient
    from explorator.domain.intent.parser import SoftPreferences  # noqa: F401  (registered builder)

    client = FakeLLMClient()
    with usage.track_usage() as u, usage.set_phase("parse_intent"):
        await client.generate_structured("p", SoftPreferences, tier=ModelTier.FLASH)
    assert u.totals()["total"] > 0
    assert u.by_phase["parse_intent"].calls == 1


async def test_instrument_sets_phase_and_emits_on_change() -> None:
    from explorator.engine.graph import _instrument

    emitted: list[tuple[str, dict]] = []

    async def on_progress(event_type: str, data: dict) -> None:
        emitted.append((event_type, data))

    async def fake_node(state: dict) -> dict:
        # Simulate an LLM call attributed to this node's phase.
        usage.record_tokens("gemini-pro-latest", 300, 100)
        return {}

    wrapped = _instrument("generate", fake_node)

    with usage.track_usage() as u:
        await wrapped({"on_progress": on_progress, "round_number": 1})

    assert u.by_phase["generate"].input == 300
    assert emitted and emitted[0][0] == "token_usage"
    assert emitted[0][1]["total_tokens"] == 400


async def test_instrument_skips_emit_when_unchanged() -> None:
    from explorator.engine.graph import _instrument

    emitted: list[tuple[str, dict]] = []

    async def on_progress(event_type: str, data: dict) -> None:
        emitted.append((event_type, data))

    async def deterministic_node(state: dict) -> dict:
        return {}  # no token usage

    wrapped = _instrument("assemble", deterministic_node)
    with usage.track_usage():
        await wrapped({"on_progress": on_progress, "round_number": 1})

    assert emitted == []


async def test_concurrent_gather_attributes_to_one_phase() -> None:
    import asyncio

    async def one_call(i: int) -> None:
        usage.record_tokens("gemini-flash-latest", 100, 20)

    with usage.track_usage() as u, usage.set_phase("evaluate_progressions"):
        await asyncio.gather(*(one_call(i) for i in range(5)))

    # All 5 concurrent calls attribute to the single phase set by the parent.
    assert u.by_phase["evaluate_progressions"].calls == 5
    assert u.by_phase["evaluate_progressions"].input == 500
    assert u.totals()["total"] == 600


async def test_revisited_phase_accumulates_across_loop() -> None:
    # Simulates the mutation loop re-entering the same phase node twice.
    with usage.track_usage() as u:
        with usage.set_phase("evaluate_progressions"):
            usage.record_tokens("gemini-flash-latest", 100, 40)
        with usage.set_phase("mutate"):
            usage.record_tokens("gemini-pro-latest", 200, 80)
        with usage.set_phase("evaluate_progressions"):
            usage.record_tokens("gemini-flash-latest", 100, 40)

    assert u.by_phase["evaluate_progressions"].calls == 2
    assert u.by_phase["evaluate_progressions"].input == 200
    assert u.by_phase["mutate"].calls == 1


async def test_synthetic_flag_surfaces_in_event() -> None:
    with usage.track_usage() as u, usage.set_phase("parse_intent"):
        usage.record_synthetic_tokens("gemini-flash-latest", 800, 200)
    event = u.to_event(1)
    assert event["is_synthetic"] is True
    # Real recording leaves it False.
    with usage.track_usage() as u2:
        usage.record_tokens("gemini-pro-latest", 10, 5)
    assert u2.to_event(1)["is_synthetic"] is False


def test_explicit_tier_overrides_name_heuristic() -> None:
    # "qwen3:8b" has no "flash" in it — the heuristic would call it pro.
    with usage.track_usage() as u, usage.set_phase("plan_voicings"):
        usage.record_tokens("qwen3:8b", 100, 10, tier="flash")
    assert set(u.by_model) == {"flash"}
    assert u.by_phase["plan_voicings"].model == "flash"


def test_record_fallback_counts_and_is_noop_outside_scope() -> None:
    usage.record_fallback("plan_voicings")  # no scope → no error
    with usage.track_usage() as u:
        usage.record_fallback("plan_voicings")
        usage.record_fallback("plan_voicings")
        usage.record_fallback("generate_melody")
    assert u.fallbacks == {"plan_voicings": 2, "generate_melody": 1}
    assert u.to_event(1)["fallbacks"] == {"plan_voicings": 2, "generate_melody": 1}


def test_to_event_reports_priced_for_gemini_defaults() -> None:
    with usage.track_usage() as u:
        usage.record_tokens("gemini-pro-latest", 1, 1)
    assert u.to_event(1)["is_priced"] is True
    assert u.to_event(1)["fallbacks"] == {}


def test_unpriced_provider_reports_zero_cost_and_not_priced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from explorator.config import settings

    for name in (
        "llm_price_pro_input",
        "llm_price_pro_output",
        "llm_price_flash_input",
        "llm_price_flash_output",
    ):
        monkeypatch.setattr(settings, name, None)
    with usage.track_usage() as u:
        usage.record_tokens("qwen3:32b", 1_000_000, 1_000_000, tier="pro")
    event = u.to_event(1)
    assert event["is_priced"] is False
    assert event["estimated_cost_usd"] == 0
