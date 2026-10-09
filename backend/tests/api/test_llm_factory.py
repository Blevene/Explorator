"""Provider selection in the LLM client factory."""

from collections.abc import Iterator

import pytest

from explorator.adapters.gemini import GeminiClient
from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.adapters.openai_compat import OpenAICompatClient
from explorator.api.deps import get_gemini_client, get_llm_client
from explorator.config import settings


@pytest.fixture(autouse=True)
def _fresh_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("GEMINI_MOCK", raising=False)
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


def test_legacy_name_is_same_function() -> None:
    assert get_gemini_client is get_llm_client


def test_mock_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MOCK", "true")
    monkeypatch.setattr(settings, "llm_provider", "openai")
    assert isinstance(get_llm_client(), FakeGeminiClient)


def test_gemini_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    client = get_llm_client()
    assert isinstance(client, GeminiClient)
    assert client.pro_model == settings.llm_pro_model


def test_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_pro_model", "qwen3:32b")
    monkeypatch.setattr(settings, "llm_flash_model", "qwen3:8b")
    monkeypatch.setattr(settings, "llm_max_concurrency", 3)
    client = get_llm_client()
    assert isinstance(client, OpenAICompatClient)
    assert (client.pro_model, client.flash_model) == ("qwen3:32b", "qwen3:8b")
    assert str(client._client.base_url).startswith("http://localhost:11434/v1")
