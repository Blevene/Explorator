"""Graph-topology tests for M5d node wiring."""
from unittest.mock import MagicMock

from explorator.engine.graph import build_exploration_graph


def test_harvest_patterns_wired_between_persist_realization_and_persist_round():
    graph = build_exploration_graph(MagicMock(), MagicMock())
    nodes = set(graph.get_graph().nodes)
    assert "harvest_patterns" in nodes
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert ("persist_realization", "harvest_patterns") in edges
    assert ("harvest_patterns", "persist_round") in edges
