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

    # Generation defaults
    default_max_rounds: int = 4
    default_target_score: float = 8.5
    default_generation_mode: str = "balanced"

    # Timeouts
    gemini_timeout_seconds: int = 120
    neo4j_query_timeout_seconds: int = 5


settings = Settings()
