"""Integration test for the M2a realization pipeline."""

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def gemini():
    from explorator.adapters.gemini import GeminiClient
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    return GeminiClient(api_key=api_key)


@pytest.fixture
def mock_gemini():
    """Stub GeminiClient — sufficient for graph compilation (no API calls made)."""
    return MagicMock()


@pytest.fixture
def mock_driver():
    """Stub Neo4j driver — sufficient for graph compilation (no DB calls made)."""
    return MagicMock()


@pytest.fixture
async def driver():
    from neo4j import AsyncGraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "explorator")
    drv = AsyncGraphDatabase.driver(uri, auth=(user, password))
    yield drv
    await drv.close()


@pytest.mark.integration
def test_realization_graph_compiles(mock_gemini, mock_driver):
    """Test the realization graph compiles with all expected nodes."""
    from explorator.engine.realization_graph import build_realization_graph

    graph = build_realization_graph(mock_gemini, mock_driver)
    assert graph is not None

    # Verify graph has all expected nodes
    node_names = set(graph.nodes.keys())
    expected = {"load_context", "plan_voicings", "generate_bass", "assemble", "persist_realization"}
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


@pytest.mark.integration
def test_realization_graph_has_evaluation_nodes(mock_gemini, mock_driver):
    """Graph should include evaluate_arrangements and rank_and_select."""
    from explorator.engine.realization_graph import build_realization_graph
    graph = build_realization_graph(mock_gemini, mock_driver)
    node_names = set(graph.nodes.keys())
    expected = {
        "load_context", "plan_voicings", "generate_bass", "assemble",
        "evaluate_arrangements", "rank_and_select", "persist_realization",
    }
    assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


@pytest.mark.integration
def test_realization_state_type():
    """Verify RealizationState has all required fields."""
    from explorator.engine.realization_state import RealizationState
    import typing

    hints = typing.get_type_hints(RealizationState)
    required_fields = [
        "session_id", "progression_candidate_ids", "progression_candidates",
        "genre_profile", "creative_brief", "voicing_strategies", "voicing_plans",
        "bass_lines", "arrangement_candidates", "arrangement_families", "on_progress",
    ]
    for field in required_fields:
        assert field in hints, f"Missing field: {field}"
