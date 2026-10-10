"""Tests for Gemini adapter."""

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from explorator.adapters.gemini import GeminiClient, ModelTier


def _has_api_key() -> bool:
    import os

    return bool(os.environ.get("GEMINI_API_KEY"))


def test_model_tier_routing() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.get_model_name(ModelTier.PRO) == "gemini-pro-latest"
    assert client.get_model_name(ModelTier.FLASH) == "gemini-flash-latest"


def test_client_initialization() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.pro_model == "gemini-pro-latest"
    assert client.flash_model == "gemini-flash-latest"


class SampleResponse(BaseModel):
    name: str
    value: int


@pytest.mark.skipif(
    not _has_api_key(),
    reason="GEMINI_API_KEY not set",
)
async def test_generate_structured_returns_typed_response() -> None:
    """Integration test — requires real Gemini API key."""
    import os

    client = GeminiClient(api_key=os.environ["GEMINI_API_KEY"])
    result = await client.generate_structured(
        prompt="Return a JSON object with name='test' and value=42",
        response_model=SampleResponse,
        tier=ModelTier.FLASH,
    )
    assert isinstance(result, SampleResponse)
    assert result.name == "test"
    assert result.value == 42


def test_timeout_is_passed_to_genai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeGenaiClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("explorator.adapters.gemini.genai.Client", _FakeGenaiClient)
    GeminiClient(api_key="k", timeout_seconds=45)

    http_options = captured["http_options"]
    assert http_options.timeout == 45_000  # type: ignore[attr-defined]  # google-genai uses ms


# ── max_output_tokens + parse retry ──────────────────────────────────────────


def _response(text: str) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, cached_content_token_count=0
        ),
    )


def _client_with(*side_effect: object) -> tuple[GeminiClient, AsyncMock]:
    client = GeminiClient(api_key="test-key")
    mock = AsyncMock(side_effect=list(side_effect))
    client._client.aio.models.generate_content = mock  # type: ignore[method-assign]
    return client, mock


async def test_max_output_tokens_reaches_config() -> None:
    client, mock = _client_with(_response('{"name": "a", "value": 1}'))
    await client.generate_structured("p", SampleResponse, max_output_tokens=4096)
    assert mock.call_args.kwargs["config"].max_output_tokens == 4096


async def test_max_output_tokens_unset_by_default() -> None:
    client, mock = _client_with(_response('{"name": "a", "value": 1}'))
    await client.generate_structured("p", SampleResponse)
    assert mock.call_args.kwargs["config"].max_output_tokens is None


async def test_malformed_then_valid_retries_once() -> None:
    client, mock = _client_with(
        _response('{"name": "a", "val'), _response('{"name": "a", "value": 1}')
    )
    result = await client.generate_structured("p", SampleResponse)
    assert result == SampleResponse(name="a", value=1)
    assert mock.await_count == 2


async def test_schema_mismatch_then_valid_retries_once() -> None:
    # Well-formed JSON that fails validation (ValidationError) is retried too.
    client, mock = _client_with(_response('{"name": "a"}'), _response('{"name": "a", "value": 2}'))
    result = await client.generate_structured("p", SampleResponse)
    assert result == SampleResponse(name="a", value=2)
    assert mock.await_count == 2


async def test_malformed_twice_raises_value_error() -> None:
    client, mock = _client_with(_response("junk"), _response("more junk"))
    with pytest.raises(ValueError):
        await client.generate_structured("p", SampleResponse)
    assert mock.await_count == 2


async def test_api_error_is_not_retried() -> None:
    client, mock = _client_with(RuntimeError("504"))
    with pytest.raises(RuntimeError):
        await client.generate_structured("p", SampleResponse)
    assert mock.await_count == 1


async def test_retry_records_usage_for_each_attempt() -> None:
    from explorator.adapters import usage

    client, _ = _client_with(_response("junk"), _response('{"name": "a", "value": 1}'))
    with usage.track_usage() as u:
        await client.generate_structured("p", SampleResponse)
    assert u.totals()["input"] == 20
