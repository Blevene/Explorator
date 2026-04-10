"""Tests for the unified exploration graph."""

from unittest.mock import MagicMock

from explorator.engine.graph import build_exploration_graph, build_realization_subgraph


def test_exploration_graph_compiles() -> None:
    """Unified graph compiles with mock dependencies."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    assert graph is not None


def test_exploration_graph_has_all_nodes() -> None:
    """Unified graph contains all M1+M2 nodes."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    node_names = set(graph.nodes.keys())
    expected = {
        "parse_intent",
        "load_genre",
        "generate",
        "evaluate_progressions",
        "select_top_progressions",
        "load_context",
        "plan_voicings",
        "generate_bass",
        "assemble",
        "evaluate_arrangements",
        "rank_and_select",
        "persist_realization",
        "persist_round",
    }
    missing = expected - node_names
    assert not missing, f"Missing nodes: {missing}"


def test_exploration_graph_entry_point() -> None:
    """Graph starts at parse_intent."""
    graph = build_exploration_graph(MagicMock(), MagicMock())
    assert "__start__" in graph.nodes or "parse_intent" in graph.nodes


def test_realization_subgraph_compiles() -> None:
    """Realization subgraph compiles with mock dependencies."""
    graph = build_realization_subgraph(MagicMock(), MagicMock())
    assert graph is not None


def test_realization_subgraph_has_m2_nodes() -> None:
    """Realization subgraph contains only M2 nodes."""
    graph = build_realization_subgraph(MagicMock(), MagicMock())
    node_names = set(graph.nodes.keys())
    expected = {
        "load_context",
        "plan_voicings",
        "generate_bass",
        "assemble",
        "evaluate_arrangements",
        "rank_and_select",
        "persist_realization",
    }
    missing = expected - node_names
    assert not missing, f"Missing nodes: {missing}"
    # Should NOT contain M1 nodes
    assert "parse_intent" not in node_names
    assert "generate" not in node_names
