"""Application configuration via environment variables."""

from typing import Literal, Self

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Gemini-provider defaults (USD per 1M tokens are estimates — the models are
# *-latest aliases, so cost is surfaced as "~ estimate").
_GEMINI_DEFAULTS = {
    "llm_pro_model": "gemini-pro-latest",
    "llm_flash_model": "gemini-flash-latest",
    "llm_price_pro_input": 1.25,
    "llm_price_pro_output": 10.0,
    "llm_price_flash_input": 0.30,
    "llm_price_flash_output": 2.50,
}

# Pre-ADR-012 names still accepted; each fills its LLM_* counterpart when unset.
_LEGACY_SUFFIXES = (
    "api_key",
    "pro_model",
    "flash_model",
    "timeout_seconds",
    "price_pro_input",
    "price_pro_output",
    "price_flash_input",
    "price_flash_output",
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "explorator_dev"

    # LLM provider — see docs/decisions/012-configurable-llm-provider.md.
    # Empty string / 0 / None mean "unset"; provider defaults resolve below.
    llm_provider: Literal["gemini", "openai"] = "gemini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_pro_model: str = ""
    llm_flash_model: str = ""
    llm_timeout_seconds: int = 0
    llm_max_retries: int = 1
    llm_max_concurrency: int = 0
    llm_context_tokens: int | None = None
    llm_price_pro_input: float | None = None
    llm_price_pro_output: float | None = None
    llm_price_flash_input: float | None = None
    llm_price_flash_output: float | None = None

    # Deprecated aliases — read only to fill unset LLM_* values (logged at startup).
    gemini_api_key: str | None = None
    gemini_pro_model: str | None = None
    gemini_flash_model: str | None = None
    gemini_timeout_seconds: int | None = None
    gemini_price_pro_input: float | None = None
    gemini_price_pro_output: float | None = None
    gemini_price_flash_input: float | None = None
    gemini_price_flash_output: float | None = None

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Export
    export_dir: str = "exports"

    # Timeouts
    neo4j_query_timeout_seconds: int = 5

    _legacy_names_used: list[str] = PrivateAttr(default_factory=list)

    @property
    def legacy_names_used(self) -> list[str]:
        """Deprecated GEMINI_* env names that supplied a value."""
        return list(self._legacy_names_used)

    @model_validator(mode="after")
    def _resolve_llm(self) -> Self:
        legacy: list[str] = []
        for suffix in _LEGACY_SUFFIXES:
            new, old = f"llm_{suffix}", f"gemini_{suffix}"
            old_value = getattr(self, old)
            if old_value is None or getattr(self, new) not in ("", 0, None):
                continue
            # GEMINI_* model names never apply to a non-Gemini provider.
            if self.llm_provider != "gemini" and suffix.endswith("_model"):
                continue
            setattr(self, new, old_value)
            legacy.append(old.upper())
        self._legacy_names_used = legacy

        if self.llm_provider == "gemini":
            for name, default in _GEMINI_DEFAULTS.items():
                if getattr(self, name) in ("", None):
                    setattr(self, name, default)
            self.llm_timeout_seconds = self.llm_timeout_seconds or 120
        else:
            missing = [
                env
                for env, value in (
                    ("LLM_PRO_MODEL", self.llm_pro_model),
                    ("LLM_FLASH_MODEL", self.llm_flash_model),
                )
                if not value
            ]
            if missing:
                msg = f"LLM_PROVIDER={self.llm_provider} requires {', '.join(missing)}"
                raise ValueError(msg)
            self.llm_timeout_seconds = self.llm_timeout_seconds or 300
            self.llm_max_concurrency = self.llm_max_concurrency or 4
        return self


settings = Settings()
