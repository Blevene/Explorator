"""Tests for Gemini adapter."""

from explorator.adapters.gemini import GeminiClient, ModelTier


def test_model_tier_routing() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.get_model_name(ModelTier.PRO) == "gemini-pro-latest"
    assert client.get_model_name(ModelTier.FLASH) == "gemini-flash-latest"


def test_client_initialization() -> None:
    client = GeminiClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.pro_model == "gemini-pro-latest"
    assert client.flash_model == "gemini-flash-latest"
