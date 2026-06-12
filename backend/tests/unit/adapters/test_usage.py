"""Tests for the token-usage accumulator."""

from types import SimpleNamespace

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
    assert u.totals() == {"input": 10, "output": 0, "cached": 4, "total": 14}


def test_estimated_cost_matches_pricing() -> None:
    # Defaults: pro input 1.25/M, pro output 10.0/M.
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
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
    with usage.track_usage() as u:
        with usage.set_phase("generate"):
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

    with usage.track_usage() as u:
        with usage.set_phase("generate"):
            await client.generate_structured("p", _Sample, tier=ModelTier.PRO)

    assert u.totals() == {"input": 120, "output": 30, "cached": 0, "total": 150}
    assert u.by_phase["generate"].model == "pro"
