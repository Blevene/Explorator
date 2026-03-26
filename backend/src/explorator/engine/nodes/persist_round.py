"""Persist round node — save results to Neo4j."""

import contextlib

from neo4j import AsyncDriver

from explorator.engine.state import ExplorationState
from explorator.graph.repository import BaseRepository


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


async def persist_round(state: ExplorationState, *, driver: AsyncDriver) -> dict:
    """Save all candidates and evaluations to Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_round"})

    from explorator.models.harmony import ProgressionCandidate

    repo = ProgressionCandidateRepo(driver)

    for candidate_data in state.get("top_progressions", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)
        with contextlib.suppress(Exception):
            await repo.create(candidate)

    if callback:
        top_count = len(state.get("top_progressions", []))
        top_score = 0.0
        for s in state.get("scorecards", []):
            if s.get("weighted_total", 0) > top_score:
                top_score = s["weighted_total"]

        await callback(
            "round_completed",
            {
                "round": state.get("round_number", 1),
                "candidates_count": top_count,
                "top_score": round(top_score, 2),
                "stop_met": True,  # M1 is single-round
            },
        )

    return {}
