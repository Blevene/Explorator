"""FastAPI dependency injection."""

import os
from functools import lru_cache

from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.config import settings
from explorator.graph.connection import get_driver
from explorator.graph.genre_research_repo import GenreResearchRepository
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


async def get_genre_research_repo() -> GenreResearchRepository:
    """Get genre research repository dependency."""
    driver = await get_driver()
    return GenreResearchRepository(driver)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton. Returns FakeGeminiClient when GEMINI_MOCK=true."""
    if os.environ.get("GEMINI_MOCK", "").lower() == "true":
        from explorator.adapters.gemini_mock import FakeGeminiClient
        return FakeGeminiClient()  # type: ignore[return-value]
    return GeminiClient(
        api_key=settings.gemini_api_key,
        pro_model=settings.gemini_pro_model,
        flash_model=settings.gemini_flash_model,
        timeout_seconds=settings.gemini_timeout_seconds,
    )


async def get_pattern_library_repo():
    """Get pattern library repository dependency."""
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    driver = await get_driver()
    return PatternLibraryRepo(driver)


async def get_harvest_repos():
    """Compose the HarvestRepos bundle for POST /v1/sessions/{id}/finalists/harvest."""
    from explorator.graph.arrangement_candidate_repo import ArrangementCandidateRepo
    from explorator.graph.bass_line_repo import BassLineRepo
    from explorator.graph.groove_pattern_repo import GroovePatternRepo
    from explorator.graph.melodic_complement_repo import MelodicComplementRepo
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.graph.voicing_plan_repo import VoicingPlanRepo
    from explorator.services.pattern_library.harvest_service import HarvestRepos

    driver = await get_driver()
    return HarvestRepos(
        pattern_library=PatternLibraryRepo(driver),
        arrangement_candidate=ArrangementCandidateRepo(driver),
        voicing_plan=VoicingPlanRepo(driver),
        bass_line=BassLineRepo(driver),
        groove_pattern=GroovePatternRepo(driver),
        melodic_complement=MelodicComplementRepo(driver),
    )
