"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from explorator.api.middleware import AuthStubMiddleware
from explorator.api.routes import genres, sessions
from explorator.graph.connection import close_driver, get_driver
from explorator.graph.schema import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: init Neo4j schema on startup, close on shutdown."""
    driver = await get_driver()
    await init_schema(driver)
    yield
    await close_driver()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MusicExplorator",
        description="Genre-aware musical exploration engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthStubMiddleware)

    app.include_router(sessions.router, prefix="/v1")
    app.include_router(genres.router, prefix="/v1")

    return app
