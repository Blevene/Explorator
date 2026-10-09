"""FastAPI dependency injection.

Every repo dependency obtains the driver via ``get_optional_driver()`` (which may
return ``None`` when Neo4j is unavailable) and constructs the matching repo through
the persistence factory. With ``driver is None`` the factory yields memory/null
repos, so the app degrades gracefully instead of failing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from explorator.adapters.gemini import GeminiClient
from explorator.config import settings
from explorator.graph.connection import get_optional_driver
from explorator.persistence.factory import (
    make_arrangement_candidate_repo,
    make_bass_line_repo,
    make_genre_research_repo,
    make_groove_pattern_repo,
    make_melodic_complement_repo,
    make_pattern_library_repo,
    make_session_repo,
    make_style_repo,
    make_voicing_plan_repo,
)

if TYPE_CHECKING:
    from neo4j import AsyncDriver

    from explorator.graph.genre_research_repo import GenreResearchRepository
    from explorator.graph.pattern_library_repo import PatternLibraryRepo
    from explorator.graph.session_repo import SessionRepository
    from explorator.graph.style_repo import StyleRepository
    from explorator.persistence.memory_repos import (
        MemorySessionRepo,
        MemoryStyleRepo,
    )
    from explorator.persistence.null_repos import (
        NullGenreResearchRepo,
        NullPatternLibraryRepo,
    )
    from explorator.services.pattern_library.harvest_service import HarvestRepos


async def get_neo4j_driver() -> AsyncDriver | None:
    """Get the Neo4j driver dependency, or ``None`` in memory mode.

    Routes that depend on this may receive ``None``; they must construct repos
    via the persistence factory (which handles the None case) and guard any
    direct-Cypher block behind ``if driver is not None:``.
    """
    return await get_optional_driver()


async def get_session_repo() -> SessionRepository | MemorySessionRepo:
    """Get session repository dependency."""
    driver = await get_optional_driver()
    return make_session_repo(driver)


async def get_style_repo() -> StyleRepository | MemoryStyleRepo:
    """Get style repository dependency (YAML-backed in memory mode)."""
    driver = await get_optional_driver()
    return make_style_repo(driver)


async def get_genre_research_repo() -> GenreResearchRepository | NullGenreResearchRepo:
    """Get genre research repository dependency."""
    driver = await get_optional_driver()
    return make_genre_research_repo(driver)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton. Returns FakeGeminiClient when GEMINI_MOCK=true."""
    if os.environ.get("GEMINI_MOCK", "").lower() == "true":
        from explorator.adapters.gemini_mock import FakeGeminiClient
        return FakeGeminiClient()  # type: ignore[return-value]
    return GeminiClient(
        api_key=settings.llm_api_key,
        pro_model=settings.llm_pro_model,
        flash_model=settings.llm_flash_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


async def get_pattern_library_repo() -> PatternLibraryRepo | NullPatternLibraryRepo:
    """Get pattern library repository dependency (null/no-op in memory mode)."""
    driver = await get_optional_driver()
    return make_pattern_library_repo(driver)


async def get_harvest_repos() -> HarvestRepos:
    """Compose the HarvestRepos bundle for POST /v1/sessions/{id}/finalists/harvest.

    In memory mode the pattern-library repo is a null no-op (harvest upserts
    become no-ops) while the generation-path repos are in-memory, so harvest
    completes cleanly with ``upserted_count=0``.
    """
    from explorator.services.pattern_library.harvest_service import HarvestRepos

    driver = await get_optional_driver()
    return HarvestRepos(
        pattern_library=make_pattern_library_repo(driver),
        arrangement_candidate=make_arrangement_candidate_repo(driver),
        voicing_plan=make_voicing_plan_repo(driver),
        bass_line=make_bass_line_repo(driver),
        groove_pattern=make_groove_pattern_repo(driver),
        melodic_complement=make_melodic_complement_repo(driver),
    )
