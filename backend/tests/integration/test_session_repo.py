"""Integration tests for session repository."""

from neo4j import AsyncDriver

from explorator.graph.session_repo import SessionRepository
from explorator.models.session import Session


async def test_create_and_read_session(neo4j_driver: AsyncDriver) -> None:
    repo = SessionRepository(neo4j_driver)
    session = Session(
        id="sess_test_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    await repo.create(session)
    result = await repo.get_by_id("sess_test_01")
    assert result is not None
    assert result["id"] == "sess_test_01"
    assert result["status"] == "active"
    assert result["mode"] == "full_exploration"


async def test_list_sessions(neo4j_driver: AsyncDriver) -> None:
    repo = SessionRepository(neo4j_driver)
    for i in range(3):
        session = Session(
            id=f"sess_list_{i}",
            type="session",
            status="active",
            mode="full_exploration",
        )
        await repo.create(session)
    results = await repo.list_sessions()
    assert len(results) == 3


async def test_update_session_status(neo4j_driver: AsyncDriver) -> None:
    repo = SessionRepository(neo4j_driver)
    session = Session(
        id="sess_update_01",
        type="session",
        status="active",
        mode="full_exploration",
    )
    await repo.create(session)
    await repo.update_status("sess_update_01", "completed")
    result = await repo.get_by_id("sess_update_01")
    assert result is not None
    assert result["status"] == "completed"
