"""Shared fixtures for API tests."""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from explorator.api.app import create_app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]
