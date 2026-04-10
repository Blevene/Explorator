"""LangGraph unified exploration graph — M1 + M2 pipeline.

Full flow: parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble → evaluate_arrangements
  → rank_and_select → persist_realization → persist_round → END
"""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.assemble_arrangements import assemble_arrangements
from explorator.engine.nodes.evaluate_arrangements import evaluate_arrangements
from explorator.engine.nodes.evaluate_progressions import evaluate_progressions
from explorator.engine.nodes.generate import generate
from explorator.engine.nodes.generate_bass import generate_bass
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.load_genre import load_genre
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.persist_round import persist_round
from explorator.engine.nodes.plan_voicings import plan_voicings
from explorator.engine.nodes.rank_and_select import rank_and_select
from explorator.engine.nodes.select_top_progressions import select_top_progressions
from explorator.engine.state import ExplorationState


def _add_m2_nodes(
    graph: StateGraph,
    gemini: GeminiClient,
    driver: AsyncDriver,
) -> None:
    """Register M2 realization nodes on a graph. Shared by full and sub-graph builders."""
    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))


def _add_m2_edges(graph: StateGraph) -> None:
    """Wire M2 realization edges. Shared by full and sub-graph builders."""
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")
    graph.add_edge("rank_and_select", "persist_realization")


def build_exploration_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the unified M1+M2 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # M1 nodes
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)

    # M2 nodes (shared registration)
    _add_m2_nodes(graph, gemini, driver)

    # Persistence
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Linear flow: M1 → M2 → persist
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "load_context")
    _add_m2_edges(graph)
    graph.add_edge("persist_realization", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()


def build_realization_subgraph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build M2-only subgraph for independent realization (used by realization endpoint)."""
    graph = StateGraph(ExplorationState)

    _add_m2_nodes(graph, gemini, driver)

    graph.set_entry_point("load_context")
    _add_m2_edges(graph)
    graph.add_edge("persist_realization", END)

    return graph.compile()
