"""LangGraph genre research graph — 6-node agentic pipeline.

Flow: research → draft → critique → [refine loop] → validate → output → END
"""

from functools import partial
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from neo4j import AsyncDriver

from explorator.adapters.gemini import GeminiClient
from explorator.engine.nodes.genre_research.critique import critique_draft
from explorator.engine.nodes.genre_research.draft import draft_yamls
from explorator.engine.nodes.genre_research.output import output_draft
from explorator.engine.nodes.genre_research.refine import refine_draft
from explorator.engine.nodes.genre_research.research import research_genre
from explorator.engine.nodes.genre_research.validate import validate_draft
from explorator.engine.state import ProgressCallback


class GenreResearchState(TypedDict, total=False):
    """State for the genre research pipeline."""

    job_id: str
    genre_name: str
    reference_artists: list[str]

    # Step outputs
    research_log: str
    draft_yamls: dict[str, Any]
    critique_trail: list[dict[str, Any]]
    refine_iteration: int
    needs_refine: bool
    validation_errors: list[str]

    # Control
    status: str
    on_progress: ProgressCallback


def route_after_critique(state: dict[str, Any]) -> str:
    """Route: refine if needed and under iteration cap, else validate."""
    if state.get("needs_refine") and state.get("refine_iteration", 0) < 2:
        return "refine"
    return "validate"


def route_after_validate(state: dict[str, Any]) -> str:
    """Always route to output — validation errors surfaced in review UI."""
    return "output"


def build_genre_research_graph(gemini: GeminiClient, driver: AsyncDriver) -> Any:
    """Build and compile the genre research LangGraph pipeline."""
    graph = StateGraph(GenreResearchState)

    graph.add_node("research", partial(research_genre, gemini=gemini, driver=driver))
    graph.add_node("draft", partial(draft_yamls, gemini=gemini, driver=driver))
    graph.add_node("critique", partial(critique_draft, gemini=gemini, driver=driver))
    graph.add_node("refine", partial(refine_draft, gemini=gemini, driver=driver))
    graph.add_node("validate", partial(validate_draft, driver=driver))
    graph.add_node("output", partial(output_draft, driver=driver))

    graph.set_entry_point("research")
    graph.add_edge("research", "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges("critique", route_after_critique, {
        "refine": "refine",
        "validate": "validate",
    })
    graph.add_edge("refine", "critique")
    graph.add_conditional_edges("validate", route_after_validate, {
        "output": "output",
    })
    graph.add_edge("output", END)

    return graph.compile()
