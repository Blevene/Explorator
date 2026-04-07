"""Build and compile the M2a realization LangGraph flow."""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.assemble_arrangements import assemble_arrangements
from explorator.engine.nodes.evaluate_arrangements import evaluate_arrangements
from explorator.engine.nodes.generate_bass import generate_bass
from explorator.engine.nodes.load_context import load_context
from explorator.engine.nodes.persist_realization import persist_realization
from explorator.engine.nodes.plan_voicings import plan_voicings
from explorator.engine.nodes.rank_and_select import rank_and_select
from explorator.engine.realization_state import RealizationState


def build_realization_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    graph = StateGraph(RealizationState)

    graph.add_node("load_context", partial(load_context, driver=driver))
    graph.add_node("plan_voicings", partial(plan_voicings, gemini=gemini))
    graph.add_node("generate_bass", generate_bass)
    graph.add_node("assemble", assemble_arrangements)
    graph.add_node("evaluate_arrangements", evaluate_arrangements)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("persist_realization", partial(persist_realization, driver=driver))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "plan_voicings")
    graph.add_edge("plan_voicings", "generate_bass")
    graph.add_edge("generate_bass", "assemble")
    graph.add_edge("assemble", "evaluate_arrangements")
    graph.add_edge("evaluate_arrangements", "rank_and_select")
    graph.add_edge("rank_and_select", "persist_realization")
    graph.add_edge("persist_realization", END)

    return graph.compile()
