"""Integration test for the full M1 engine flow.

Requires: Neo4j running, Gemini API key set.
"""

import os

import pytest
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.domain.style.service import StyleService
from explorator.engine.graph import build_exploration_graph


def _has_api_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.skipif(not _has_api_key(), reason="GEMINI_API_KEY not set")
async def test_m1_full_flow(neo4j_driver: AsyncDriver) -> None:
    """Run the full M1 flow: parse → genre → generate → evaluate → select → persist."""
    # Sync genres first
    style = StyleService(neo4j_driver)
    await style.sync_genres_to_neo4j()

    llm = GeminiClient(api_key=os.environ["GEMINI_API_KEY"])
    graph = build_exploration_graph(llm, neo4j_driver)

    initial_state = {
        "session_id": "sess_test_m1",
        "prompt": "Dream pop in A major, wistful and haunted, 8 bars",
        "generation_mode": "conservative",
        "round_number": 1,
        "n_candidates": 4,  # Small for testing
        "k_selection": 2,
    }

    result = await graph.ainvoke(initial_state)

    # Verify outputs
    assert "creative_brief" in result
    assert result["creative_brief"]["genre"] == "dream_pop"
    assert "genre_profile" in result
    assert "progression_candidates" in result
    assert len(result["progression_candidates"]) > 0
    assert "top_progressions" in result
    assert len(result["top_progressions"]) <= 2
    assert "scorecards" in result

    # Verify candidates have chord events
    for candidate in result["top_progressions"]:
        assert "chord_events" in candidate
        assert len(candidate["chord_events"]) > 0
