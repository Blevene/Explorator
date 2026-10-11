"""Provider selection in the LLM client factory."""

from collections.abc import Iterator

import pytest

from explorator.adapters.gemini import GeminiClient
from explorator.adapters.gemini_mock import FakeGeminiClient
from explorator.adapters.openai_compat import OpenAICompatClient
from explorator.api.deps import get_gemini_client, get_llm_client
from explorator.config import Settings, settings


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
    # genai.Client rejects an empty key; don't depend on a developer's .env.
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    client = get_llm_client()
    assert isinstance(client, GeminiClient)
    assert client.pro_model == settings.llm_pro_model


def test_openai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "llm_pro_model", "qwen3:32b")
    monkeypatch.setattr(settings, "llm_flash_model", "qwen3:8b")
    monkeypatch.setattr(settings, "llm_max_concurrency", 3)
    monkeypatch.setattr(settings, "llm_extra_body", {"chat_template_kwargs": {"thinking": False}})
    client = get_llm_client()
    assert isinstance(client, OpenAICompatClient)
    assert (client.pro_model, client.flash_model) == ("qwen3:32b", "qwen3:8b")
    assert str(client._client.base_url).startswith("http://localhost:11434/v1")
    assert client._semaphore._value == 3
    assert client.extra_body == {"chat_template_kwargs": {"thinking": False}}


def test_default_gemini_timeout_reaches_genai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith(("LLM_", "GEMINI_")) and key != "GEMINI_MOCK":
            monkeypatch.delenv(key)
    default = Settings(_env_file=None)  # type: ignore[call-arg]
    for name in ("llm_provider", "llm_api_key", "llm_pro_model", "llm_flash_model",
                 "llm_timeout_seconds"):
        monkeypatch.setattr(settings, name, getattr(default, name))
    captured: dict[str, object] = {}

    class _FakeGenaiClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("explorator.adapters.gemini.genai.Client", _FakeGenaiClient)
    assert isinstance(get_llm_client(), GeminiClient)
    assert captured["http_options"].timeout == 120_000  # type: ignore[attr-defined]
