"""State type for the M2a realization LangGraph pipeline."""
from typing import Any, TypedDict


class RealizationState(TypedDict, total=False):
    session_id: str
    progression_candidate_ids: list[str]
    progression_candidates: list[dict[str, Any]]
    genre_profile: dict[str, Any]
    creative_brief: dict[str, Any]
    voicing_strategies: list[dict[str, Any]]
    voicing_plans: list[dict[str, Any]]
    bass_lines: list[dict[str, Any]]
    arrangement_candidates: list[dict[str, Any]]
    arrangement_families: list[dict[str, Any]]
    on_progress: Any
