"""FastAPI dependency injection."""

from functools import lru_cache

from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.config import settings
from explorator.graph.connection import get_driver
from explorator.graph.session_repo import SessionRepository
from explorator.graph.style_repo import StyleRepository


async def get_neo4j_driver() -> AsyncDriver:
    """Get Neo4j driver dependency."""
    return await get_driver()


async def get_session_repo() -> SessionRepository:
    """Get session repository dependency."""
    driver = await get_driver()
    return SessionRepository(driver)


async def get_style_repo() -> StyleRepository:
    """Get style repository dependency."""
    driver = await get_driver()
    return StyleRepository(driver)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton."""
    return GeminiClient(
        api_key=settings.gemini_api_key,
        pro_model=settings.gemini_pro_model,
        flash_model=settings.gemini_flash_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )
