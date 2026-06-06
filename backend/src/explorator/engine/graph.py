"""LangGraph unified exploration graph — M1 + M2 + M3a pipeline.

Full flow: parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble → evaluate_arrangements
  → rank_and_select → check_stop → (persist_realization | mutate)
  → persist_realization → persist_round → END
"""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.assemble_arrangements import assemble_arrangements
from explorator.engine.nodes.check_stop import check_stop
from explorator.engine.nodes.evaluate_arrangements import evaluate_arrangements
from explorator.engine.nodes.evaluate_progressions import evaluate_progressions
from explorator.engine.nodes.generate import generate
from explorator.engine.nodes.generate_bass import generate_bass
from explorator.engine.nodes.generate_groove import generate_groove
from explorator.engine.nodes.generate_melody import generate_melody
from explorator.engine.nodes.harvest_patterns import harvest_patterns
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.load_genre import load_genre
from explorator.engine.nodes.load_memory import load_memory
from explorator.engine.nodes.mutate import mutate
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.persist_round import persist_round
from explorator.engine.nodes.plan_voicings import plan_voicings
from explorator.engine.nodes.rank_and_select import rank_and_select
from explorator.engine.nodes.select_top_progressions import select_top_progressions
from explorator.engine.state import ExplorationState
from explorator.persistence.factory import make_pattern_library_repo


def _add_m2_nodes(
    graph: StateGraph[Any],
    gemini: GeminiClient,
    driver: AsyncDriver | None,
) -> None:
    """Register M2 realization nodes on a graph. Shared by full and sub-graph builders."""
    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("generate_groove", generate_groove)
    graph.add_node("generate_melody", partial(generate_melody, gemini=gemini))
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))


def _add_m2_edges(graph: StateGraph[Any]) -> None:
    """Wire M2 realization edges up to rank_and_select. Shared by full and sub-graph builders.

    Note: the edge FROM rank_and_select is intentionally omitted here — callers wire it
    differently (full graph uses conditional routing; subgraph goes straight to persist).
    """
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "generate_groove")
    graph.add_edge("generate_groove", "generate_melody")
    graph.add_edge("generate_melody", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")


def _route_after_stop(state: ExplorationState) -> str:
    """Route based on stop condition: persist or mutate."""
    if state.get("stop_condition_met", False):
        return "persist_realization"
    return "mutate"


def _route_after_mutate(state: ExplorationState) -> str:
    """Route based on current round's mutation scope."""
    scope = state.get("last_mutation_scope", "harmonic")
    if scope == "harmonic":
        return "evaluate_progressions"
    return "evaluate_arrangements"


def build_exploration_graph(gemini: GeminiClient, driver: AsyncDriver | None) -> Any:
    """Build and compile the unified M1+M2 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # M1 nodes
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)

    # M3b: memory/feedback node
    graph.add_node("load_memory", partial(load_memory, driver=driver))

    # M2 nodes (shared registration)
    _add_m2_nodes(graph, gemini, driver)

    # M5d-1: auto-harvest finalist patterns between persist_realization and persist_round.
    # In memory mode this is a NullPatternLibraryRepo (no-op upsert → 0 harvested);
    # harvest_patterns accepts either repo type.
    pattern_repo = make_pattern_library_repo(driver)
    graph.add_node("harvest_patterns", partial(harvest_patterns, repo=pattern_repo))

    # Persistence
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Linear flow: M1 → M2 → persist
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "load_memory")
    graph.add_edge("load_memory", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "load_context")
    _add_m2_edges(graph)

    # M3a: mutation loop
    graph.add_node("check_stop", check_stop)
    graph.add_node("mutate", partial(mutate, gemini=gemini))

    graph.add_edge("rank_and_select", "check_stop")

    # Conditional: stop → persist, continue → mutate
    graph.add_conditional_edges("check_stop", _route_after_stop, {
        "persist_realization": "persist_realization",
        "mutate": "mutate",
    })

    # Conditional: harmonic → evaluate_progressions, arrangement → evaluate_arrangements
    graph.add_conditional_edges("mutate", _route_after_mutate, {
        "evaluate_progressions": "evaluate_progressions",
        "evaluate_arrangements": "evaluate_arrangements",
    })

    graph.add_edge("persist_realization", "harvest_patterns")
    graph.add_edge("harvest_patterns", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()


def build_realization_subgraph(gemini: GeminiClient, driver: AsyncDriver | None) -> Any:
    """Build M2-only subgraph for independent realization (used by realization endpoint)."""
    graph = StateGraph(ExplorationState)

    _add_m2_nodes(graph, gemini, driver)

    graph.set_entry_point("load_context")
    _add_m2_edges(graph)
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", END)

    return graph.compile()
