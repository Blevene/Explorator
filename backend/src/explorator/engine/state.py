"""LangGraph exploration state definition."""

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

# async callback: (event_type, data) -> None
ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class ExplorationState(TypedDict, total=False):
    """Shared state passed through all LangGraph nodes.

    Uses total=False so nodes can incrementally populate fields.
    """

    # Session context
    session_id: str
    prompt: str
    genre: str
    generation_mode: str

    # Parsed intent
    creative_brief: dict[str, Any]

    # Genre data (loaded from Neo4j)
    genre_profile: dict[str, Any]
    harmonic_grammar: dict[str, Any]
    genre_rules: list[dict[str, Any]]

    # Generation outputs
    progression_candidates: list[dict[str, Any]]
    top_progressions: list[dict[str, Any]]

    # Evaluation outputs
    evaluations: list[dict[str, Any]]
    scorecards: list[dict[str, Any]]

    # --- Realization (merged from RealizationState) ---
    progression_candidate_ids: list[str]
    voicing_strategies: list[dict[str, Any]]
    voicing_plans: list[dict[str, Any]]
    bass_lines: list[dict[str, Any]]
    groove_patterns: list[dict[str, Any]]
    melodic_complements: list[dict[str, Any]]
    arrangement_candidates: list[dict[str, Any]]
    arrangement_families: list[dict[str, Any]]
    selected_arrangements: list[dict[str, Any]]

    # --- M3a: Search & Mutation ---
    search_plan: dict[str, Any]
    mutation_records: list[dict[str, Any]]
    stop_condition_met: bool
    stop_reason: str  # "quality" | "budget" | "diversity" | ""
    last_mutation_scope: str  # "harmonic" | "arrangement" | "" — set by mutate node
    pareto_front: dict[str, Any]
    all_candidates_history: list[dict[str, Any]]

    # Search control
    round_number: int
    n_candidates: int
    k_selection: int

    # --- M3c: Finalists ---
    final_selection: dict[str, Any]

    # --- M3b: Feedback & Memory ---
    feedback_history: list[dict[str, Any]]
    objective_weights: dict[str, Any]
    user_preference_profile: dict[str, Any]

    # --- M4b: Provenance ---
    provenance_events: list[dict[str, Any]]

    # Progress callback
    on_progress: ProgressCallback
