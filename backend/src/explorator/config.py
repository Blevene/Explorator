"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7688"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "explorator_dev"

    # Gemini
    gemini_api_key: str = ""
    gemini_pro_model: str = "gemini-pro-latest"
    gemini_flash_model: str = "gemini-flash-latest"

    # Gemini pricing (USD per 1M tokens) — defaults are estimates; the models are
    # *-latest aliases, so cost is surfaced as "~ estimate". Override via env.
    gemini_price_pro_input: float = 1.25
    gemini_price_pro_output: float = 10.0
    gemini_price_flash_input: float = 0.30
    gemini_price_flash_output: float = 2.50

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Export
    export_dir: str = "exports"

    # Timeouts
    gemini_timeout_seconds: int = 120
    neo4j_query_timeout_seconds: int = 5


settings = Settings()
