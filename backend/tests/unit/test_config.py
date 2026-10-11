"""Tests for LLM provider settings resolution."""

import pytest
from pydantic import ValidationError

from explorator.config import Settings


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith(("LLM_", "GEMINI_")) and key not in ("GEMINI_MOCK", "LLM_MOCK"):
            monkeypatch.delenv(key)


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_gemini_defaults_match_previous_behaviour() -> None:
    s = _settings()
    assert s.llm_provider == "gemini"
    assert s.llm_pro_model == "gemini-pro-latest"
    assert s.llm_flash_model == "gemini-flash-latest"
    assert s.llm_timeout_seconds == 120
    assert (s.llm_price_pro_input, s.llm_price_pro_output) == (1.25, 10.0)
    assert (s.llm_price_flash_input, s.llm_price_flash_output) == (0.30, 2.50)
    assert s.legacy_names_used == []


def test_legacy_gemini_env_names_are_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-key")
    monkeypatch.setenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("GEMINI_PRICE_PRO_INPUT", "2.0")
    s = _settings()
    assert s.llm_api_key == "legacy-key"
    assert s.llm_pro_model == "gemini-2.5-pro"
    assert s.llm_timeout_seconds == 90
    assert s.llm_price_pro_input == 2.0
    assert set(s.legacy_names_used) == {
        "GEMINI_API_KEY", "GEMINI_PRO_MODEL", "GEMINI_TIMEOUT_SECONDS", "GEMINI_PRICE_PRO_INPUT",
    }


def test_new_name_wins_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "old")
    monkeypatch.setenv("LLM_API_KEY", "new")
    s = _settings()
    assert s.llm_api_key == "new"
    assert "GEMINI_API_KEY" not in s.legacy_names_used


def test_openai_provider_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_PRO_MODEL", "qwen3:32b")
    monkeypatch.setenv("LLM_FLASH_MODEL", "qwen3:8b")
    s = _settings()
    assert s.llm_timeout_seconds == 300
    assert s.llm_max_concurrency == 4
    assert s.llm_max_retries == 1
    assert s.llm_price_pro_input is None  # unpriced → "not priced" in the UI
    assert s.llm_context_tokens is None


def test_openai_without_models_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PRO_MODEL", "qwen3:32b")
    with pytest.raises(ValidationError, match="LLM_FLASH_MODEL"):
        _settings()


def test_unknown_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with pytest.raises(ValidationError):
        _settings()


def test_openai_ignores_gemini_model_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Legacy GEMINI_* model names must not leak into an openai config.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("GEMINI_PRO_MODEL", "gemini-pro-latest")
    monkeypatch.setenv("LLM_FLASH_MODEL", "qwen3:8b")
    with pytest.raises(ValidationError, match="LLM_PRO_MODEL"):
        _settings()


def test_openai_ignores_all_legacy_gemini_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PRO_MODEL", "qwen3:32b")
    monkeypatch.setenv("LLM_FLASH_MODEL", "qwen3:8b")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.setenv("GEMINI_PRICE_PRO_INPUT", "1.25")
    s = _settings()
    assert s.llm_api_key == ""
    assert s.llm_price_pro_input is None
    assert s.legacy_names_used == []


def test_explicit_zero_price_beats_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PRICE_PRO_INPUT", "0")
    monkeypatch.setenv("GEMINI_PRICE_PRO_INPUT", "1.25")
    s = _settings()
    assert s.llm_price_pro_input == 0.0
    assert "GEMINI_PRICE_PRO_INPUT" not in s.legacy_names_used


def test_ignored_legacy_names_reported_for_non_gemini_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    s = _settings(llm_provider="openai", llm_pro_model="a", llm_flash_model="b")
    assert s.ignored_legacy_names == ["GEMINI_API_KEY"]
    assert s.legacy_names_used == []
    assert s.llm_api_key == ""


def test_extra_body_defaults_to_empty() -> None:
    assert _settings().llm_extra_body == {}


def test_extra_body_parses_json_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"chat_template_kwargs": {"thinking": false}}')
    assert _settings().llm_extra_body == {"chat_template_kwargs": {"thinking": False}}


# ── unknown names: ignored with a warning, never fatal ───────────────────────


def _env_file(tmp_path: object, text: str) -> str:
    from pathlib import Path

    path = Path(str(tmp_path)) / ".env"
    path.write_text(text)
    return str(path)


def test_unknown_env_file_key_does_not_stop_startup(tmp_path: object) -> None:
    s = Settings(_env_file=_env_file(tmp_path, "LLM_PROVDER=openai\n"))  # type: ignore[call-arg]
    assert s.llm_provider == "gemini"


def test_unknown_env_file_key_is_reported(tmp_path: object) -> None:
    from explorator.config import unknown_setting_warnings

    warnings = unknown_setting_warnings(_env_file(tmp_path, "LLM_PROVDER=openai\n"), environ={})
    assert len(warnings) == 1
    assert "LLM_PROVDER" in warnings[0] and "backend/.env" in warnings[0]


def test_process_env_only_names_in_env_file_get_a_hint(tmp_path: object) -> None:
    from explorator.config import unknown_setting_warnings

    text = "LLM_MOCK=true\nOPENAI_API_KEY=x\n"
    warnings = unknown_setting_warnings(_env_file(tmp_path, text), environ={})
    assert len(warnings) == 2
    assert all("process environment" in w for w in warnings)


def test_known_env_file_keys_are_not_reported(tmp_path: object) -> None:
    from explorator.config import unknown_setting_warnings

    text = "llm_provider=gemini\nLLM_API_KEY=k\nGEMINI_API_KEY=k\nNEO4J_URI=bolt://x\n"
    assert unknown_setting_warnings(_env_file(tmp_path, text), environ={}) == []


def test_unknown_llm_shell_var_is_reported() -> None:
    from explorator.config import unknown_setting_warnings

    environ = {"LLM_PROVDER": "openai", "LLM_MOCK": "true", "OPENAI_API_KEY": "x", "HOME": "/h"}
    warnings = unknown_setting_warnings(None, environ=environ)
    assert len(warnings) == 1
    assert "LLM_PROVDER" in warnings[0]


def test_missing_env_file_is_fine(tmp_path: object) -> None:
    from explorator.config import unknown_setting_warnings

    assert unknown_setting_warnings(f"{tmp_path}/absent.env", environ={}) == []
