"""Tests for the provider-neutral LLM interface."""

from explorator.adapters import gemini, llm
from explorator.adapters.gemini import GeminiClient
from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.adapters.llm import LLMClient, ModelTier


def test_model_tier_is_reexported_from_gemini() -> None:
    assert gemini.ModelTier is llm.ModelTier
    assert ModelTier.PRO.value == "pro"
    assert ModelTier.FLASH.value == "flash"


def test_clients_satisfy_protocol_statically() -> None:
    # Checked by mypy (`uv run mypy src tests/unit/adapters/test_llm.py`);
    # at runtime this just proves both construct.
    clients: list[LLMClient] = [GeminiClient(api_key="k"), FakeGeminiClient()]
    assert len(clients) == 2
