"""LangGraph unified exploration graph — M1 + M2 + M3a pipeline.

Full flow: parse_intent → load_genre → generate → evaluate_progressions
  → select_top_progressions → load_context → plan_voicings
  → generate_bass → assemble → evaluate_arrangements
  → rank_and_select → check_stop → (persist_realization | mutate)
  → persist_realization → persist_round → END
"""

import contextlib
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any, cast

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.llm import LLMClient
from explorator.adapters.usage import current_usage, set_phase
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


def _instrument[NodeFnT: Callable[[ExplorationState], Awaitable[dict[str, Any]]]](
    name: str, fn: NodeFnT
) -> NodeFnT:
    """Wrap a node to (a) attribute token usage to its phase and (b) emit a live
    ``token_usage`` SSE event when the round's cumulative tokens grew.

    Type-transparent: returns the *same* callable type it received, which
    LangGraph's ``add_node`` overloads already accept (a value typed as an
    abstract ``Callable[...]`` does not resolve those overloads, but the concrete
    node functions/partials do).

    Emit is best-effort and guarded: a failing/absent callback never breaks the
    graph. Deterministic nodes that spend no tokens emit nothing (no duplicate
    events) because ``changed_since_last_emit()`` gates the send.
    """

    async def wrapped(state: ExplorationState) -> dict[str, Any]:
        with set_phase(name):
            result = await fn(state)
        callback = state.get("on_progress")
        accumulator = current_usage()
        if (
            callback is not None
            and accumulator is not None
            and accumulator.changed_since_last_emit()
        ):
            round_number = state.get("round_number", 1)
            with contextlib.suppress(Exception):
                await callback("token_usage", accumulator.to_event(round_number))
        return result

    return cast("NodeFnT", wrapped)


def _add_m2_nodes(
    graph: StateGraph[Any],
    gemini: LLMClient,
    driver: AsyncDriver | None,
) -> None:
    """Register M2 realization nodes on a graph. Shared by full and sub-graph builders."""
    graph.add_node(
        "load_context", _instrument("load_context", partial(load_context, driver=driver))
    )
    graph.add_node(
        "plan_voicings", _instrument("plan_voicings", partial(plan_voicings, gemini=gemini))
    )
    graph.add_node("generate_bass", _instrument("generate_bass", generate_bass))
    graph.add_node("generate_groove", _instrument("generate_groove", generate_groove))
    graph.add_node(
        "generate_melody", _instrument("generate_melody", partial(generate_melody, gemini=gemini))
    )
    graph.add_node("assemble", _instrument("assemble", assemble_arrangements))
    graph.add_node(
        "evaluate_arrangements", _instrument("evaluate_arrangements", evaluate_arrangements)
    )
    graph.add_node("rank_and_select", _instrument("rank_and_select", rank_and_select))
    graph.add_node(
        "persist_realization",
        _instrument("persist_realization", partial(persist_realization, driver=driver)),
    )


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


def build_exploration_graph(gemini: LLMClient, driver: AsyncDriver | None) -> Any:
    """Build and compile the unified M1+M2 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # M1 nodes
    graph.add_node(
        "parse_intent", _instrument("parse_intent", partial(parse_intent, gemini=gemini))
    )
    graph.add_node("load_genre", _instrument("load_genre", partial(load_genre, driver=driver)))
    graph.add_node("generate", _instrument("generate", partial(generate, gemini=gemini)))
    graph.add_node(
        "evaluate_progressions",
        _instrument("evaluate_progressions", partial(evaluate_progressions, gemini=gemini)),
    )
    graph.add_node(
        "select_top_progressions", _instrument("select_top_progressions", select_top_progressions)
    )

    # M3b: memory/feedback node
    graph.add_node("load_memory", _instrument("load_memory", partial(load_memory, driver=driver)))

    # M2 nodes (shared registration)
    _add_m2_nodes(graph, gemini, driver)

    # M5d-1: auto-harvest finalist patterns between persist_realization and persist_round.
    # In memory mode this is a NullPatternLibraryRepo (no-op upsert → 0 harvested);
    # harvest_patterns accepts either repo type.
    pattern_repo = make_pattern_library_repo(driver)
    graph.add_node(
        "harvest_patterns",
        _instrument("harvest_patterns", partial(harvest_patterns, repo=pattern_repo)),
    )

    # Persistence
    graph.add_node(
        "persist_round", _instrument("persist_round", partial(persist_round, driver=driver))
    )

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
    graph.add_node("check_stop", _instrument("check_stop", check_stop))
    graph.add_node("mutate", _instrument("mutate", partial(mutate, gemini=gemini)))

    graph.add_edge("rank_and_select", "check_stop")

    # Conditional: stop → persist, continue → mutate
    graph.add_conditional_edges(
        "check_stop",
        _route_after_stop,
        {
            "persist_realization": "persist_realization",
            "mutate": "mutate",
        },
    )

    # Conditional: harmonic → evaluate_progressions, arrangement → evaluate_arrangements
    graph.add_conditional_edges(
        "mutate",
        _route_after_mutate,
        {
            "evaluate_progressions": "evaluate_progressions",
            "evaluate_arrangements": "evaluate_arrangements",
        },
    )

    graph.add_edge("persist_realization", "harvest_patterns")
    graph.add_edge("harvest_patterns", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()


def build_realization_subgraph(gemini: LLMClient, driver: AsyncDriver | None) -> Any:
    """Build M2-only subgraph for independent realization (used by realization endpoint)."""
    graph = StateGraph(ExplorationState)

    _add_m2_nodes(graph, gemini, driver)

    graph.set_entry_point("load_context")
    _add_m2_edges(graph)
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", END)

    return graph.compile()
