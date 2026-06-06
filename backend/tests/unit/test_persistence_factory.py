"""Tests for the persistence factory: driver is None ⇒ memory/null; else Neo4j."""

from neo4j import AsyncDriver

from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.graph.session_repo import SessionRepository
from explorator.persistence.factory import (
    make_pattern_library_repo,
    make_session_repo,
)
from explorator.persistence.memory_repos import MemorySessionRepo
from explorator.persistence.null_repos import NullPatternLibraryRepo


def test_session_repo_is_memory_when_no_driver() -> None:
    assert isinstance(make_session_repo(None), MemorySessionRepo)


def test_pattern_library_repo_is_null_when_no_driver() -> None:
    assert isinstance(make_pattern_library_repo(None), NullPatternLibraryRepo)


def test_session_repo_is_neo4j_when_driver(neo4j_driver: AsyncDriver) -> None:
    """``neo4j_driver`` is the unit-conftest AsyncMock(spec=AsyncDriver) fixture."""
    assert isinstance(make_session_repo(neo4j_driver), SessionRepository)


def test_pattern_library_repo_is_neo4j_when_driver(neo4j_driver: AsyncDriver) -> None:
    assert isinstance(make_pattern_library_repo(neo4j_driver), PatternLibraryRepo)
