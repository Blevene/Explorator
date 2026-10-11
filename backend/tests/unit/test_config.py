"""Tests for LLM provider settings resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from explorator.config import Settings, check_setting_names, load_settings


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


# ── unknown names ────────────────────────────────────────────────────────────


def _env_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text)
    return path


def test_unknown_llm_key_in_env_file_is_fatal(tmp_path: Path) -> None:
    # A misspelt LLM_PROVIDER would otherwise leave gemini selected and send an
    # OpenRouter/OpenAI LLM_API_KEY to Google.
    env_file = _env_file(tmp_path, "LLM_PROVDER=openai\nLLM_API_KEY=sk-or-x\n")
    with pytest.raises(ValueError, match="LLM_PROVDER.*did you mean LLM_PROVIDER"):
        check_setting_names(env_file, environ={})


def test_unknown_gemini_key_in_env_file_is_fatal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="GEMINI_APIKEY"):
        check_setting_names(_env_file(tmp_path, "GEMINI_APIKEY=k\n"), environ={})


def test_other_unknown_env_file_key_only_warns(tmp_path: Path) -> None:
    warnings = check_setting_names(_env_file(tmp_path, "export FOO=1\n"), environ={})
    assert warnings == ["FOO in backend/.env is not a setting and is ignored"]


def test_unknown_env_file_key_does_not_break_settings(tmp_path: Path) -> None:
    s = Settings(_env_file=_env_file(tmp_path, "FOO=1\n"))  # type: ignore[call-arg]
    assert s.llm_provider == "gemini"


def test_process_env_only_names_in_env_file_get_a_hint(tmp_path: Path) -> None:
    env_file = _env_file(tmp_path, "LLM_MOCK=true\nOPENAI_API_KEY=x\n")
    warnings = check_setting_names(env_file, environ={})
    assert len(warnings) == 2
    assert all("process environment" in w for w in warnings)


def test_known_env_file_keys_are_not_reported(tmp_path: Path) -> None:
    text = "llm_provider=gemini\nLLM_API_KEY=k\nGEMINI_API_KEY=k\nNEO4J_URI=bolt://x\n"
    assert check_setting_names(_env_file(tmp_path, text), environ={}) == []


def test_misspelt_shell_var_warns_with_suggestion() -> None:
    warnings = check_setting_names(None, environ={"llm_provder": "openai"})
    assert warnings == [
        "Environment variable LLM_PROVDER is not a setting and is ignored"
        " — did you mean LLM_PROVIDER?"
    ]


def test_other_tools_shell_vars_are_not_reported() -> None:
    environ = {
        "LLM_USER_PATH": "/x",  # simonw/llm
        "LLM_MOCK": "true",
        "OPENAI_API_KEY": "x",
        "HOME": "/h",
    }
    assert check_setting_names(None, environ=environ) == []


def test_missing_env_file_is_fine(tmp_path: Path) -> None:
    assert check_setting_names(tmp_path / "absent.env", environ={}) == []


def test_settings_error_mentions_likely_typo(tmp_path: Path) -> None:
    # The openai provider fails on the missing model; the hint names the typo.
    env_file = _env_file(tmp_path, "LLM_PROVIDER=openai\nLLM_FLASH_MODEL=b\n")
    with pytest.raises(ValueError, match="(?s)requires LLM_PRO_MODEL.*LLM_PRO_MODLE"):
        load_settings(env_file, environ={"LLM_PRO_MODLE": "a"})
