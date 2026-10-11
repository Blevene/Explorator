"""Tests for Gemini adapter."""

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
