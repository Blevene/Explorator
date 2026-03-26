"""Integration tests for session API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from explorator.api.app import create_app


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]


async def test_create_session(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/sessions",
        json={
            "mode": "full_exploration",
            "prompt": "Dream pop in A major, wistful and haunted, 8 bars",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["status"] == "active"


async def test_list_sessions(client: AsyncClient) -> None:
    # Create two sessions
    await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Dream pop test 1"},
    )
    await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Synthwave test 2"},
    )
    response = await client.get("/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 2


async def test_get_session(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/v1/sessions",
        json={"mode": "full_exploration", "prompt": "Cinematic test"},
    )
    session_id = create_resp.json()["session_id"]
    response = await client.get(f"/v1/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id


async def test_get_session_not_found(client: AsyncClient) -> None:
    response = await client.get("/v1/sessions/sess_DOESNOTEXIST")
    assert response.status_code == 404


async def test_list_genres(client: AsyncClient) -> None:
    response = await client.get("/v1/genres")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
