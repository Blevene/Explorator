"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from explorator.api.middleware import AuthStubMiddleware, LocalAccessGuard
from explorator.api.routes import candidates, genres, rounds, sessions
from explorator.api.routes.capabilities import router as capabilities_router
from explorator.api.routes.comparisons import router as comparisons_router
from explorator.api.routes.explanations import router as explanations_router
from explorator.api.routes.exports import router as exports_router
from explorator.api.routes.feedback import router as feedback_router
from explorator.api.routes.genre_research import router as genre_research_router
from explorator.api.routes.mutations import router as mutations_router
from explorator.api.routes.patterns import router as patterns_router
from explorator.api.routes.realization_rounds import router as realization_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Init Neo4j schema + sync genres if reachable; else run in memory mode."""
    import logging

    from explorator.graph.connection import close_driver, probe_driver

    logger = logging.getLogger(__name__)
    from explorator.config import setting_name_warnings, settings

    for warning in setting_name_warnings:
        logger.warning("%s", warning)
    for name in settings.legacy_names_used:
        logger.warning(
            "%s is deprecated — rename it to LLM_%s", name, name.removeprefix("GEMINI_")
        )
    for name in settings.ignored_legacy_names:
        logger.warning(
            "%s is ignored because LLM_PROVIDER=%s — set the LLM_* equivalent instead",
            name, settings.llm_provider,
        )
    driver = await probe_driver()
    if driver is not None:
        from explorator.domain.style.service import StyleService
        from explorator.graph.schema import init_schema

        await init_schema(driver)
        count = await StyleService(driver).sync_genres_to_neo4j()
        logger.info("Neo4j mode — synced %d genre profiles", count)
        app.state.persistence_mode = "neo4j"
    else:
        logger.warning("In-memory mode — long-term memory features disabled")
        app.state.persistence_mode = "memory"

    yield
    await close_driver()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Explorator",
        description="Genre-aware musical exploration engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # No CORS middleware: the UI reaches the API same-origin through the Vite
    # or nginx proxy, so browsers keep other sites' cross-origin reads blocked.
    app.add_middleware(AuthStubMiddleware)
    app.add_middleware(LocalAccessGuard)  # outermost: runs first

    app.include_router(capabilities_router, prefix="/v1")
    app.include_router(sessions.router, prefix="/v1")
    app.include_router(
        genre_research_router, prefix="/v1"
    )  # before genres — /genres/research, /genres/drafts must match before /genres/{name}
    app.include_router(genres.router, prefix="/v1")
    app.include_router(rounds.router, prefix="/v1")
    app.include_router(candidates.router, prefix="/v1")
    app.include_router(realization_router, prefix="/v1")
    app.include_router(mutations_router, prefix="/v1")
    app.include_router(feedback_router, prefix="/v1")
    app.include_router(exports_router, prefix="/v1")
    app.include_router(explanations_router, prefix="/v1")
    app.include_router(comparisons_router, prefix="/v1")
    app.include_router(patterns_router, prefix="/v1")

    return app
