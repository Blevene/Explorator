"""LangGraph graph definition and compilation for M1 partial flow.

M1 flow: parse_intent → load_genre → generate → evaluate_progressions
         → select_top_progressions → persist_round
"""

from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.evaluate_progressions import evaluate_progressions
from explorator.engine.nodes.generate import generate
from explorator.engine.nodes.load_genre import load_genre
from explorator.engine.nodes.parse_intent import parse_intent
from explorator.engine.nodes.persist_round import persist_round
from explorator.engine.nodes.select_top_progressions import select_top_progressions
from explorator.engine.state import ExplorationState


def build_m1_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the M1 LangGraph exploration flow."""
    graph = StateGraph(ExplorationState)

    # Add nodes with injected dependencies
    graph.add_node("parse_intent", partial(parse_intent, gemini=gemini))
    graph.add_node("load_genre", partial(load_genre, driver=driver))
    graph.add_node("generate", partial(generate, gemini=gemini))
    graph.add_node("evaluate_progressions", partial(evaluate_progressions, gemini=gemini))
    graph.add_node("select_top_progressions", select_top_progressions)
    graph.add_node("persist_round", partial(persist_round, driver=driver))

    # Define edges (linear flow for M1)
    graph.set_entry_point("parse_intent")
    graph.add_edge("parse_intent", "load_genre")
    graph.add_edge("load_genre", "generate")
    graph.add_edge("generate", "evaluate_progressions")
    graph.add_edge("evaluate_progressions", "select_top_progressions")
    graph.add_edge("select_top_progressions", "persist_round")
    graph.add_edge("persist_round", END)

    return graph.compile()
