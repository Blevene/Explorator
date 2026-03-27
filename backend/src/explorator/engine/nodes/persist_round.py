"""Persist round node — save results to Neo4j."""

import logging
from typing import Any

from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError

from explorator.engine.state import ExplorationState
from explorator.graph.repository import BaseRepository

logger = logging.getLogger(__name__)


class ProgressionCandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


async def persist_round(state: ExplorationState, *, driver: AsyncDriver) -> dict[str, Any]:
    """Save all candidates and evaluations to Neo4j."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "persist_round"})

    from explorator.models.harmony import ProgressionCandidate

    repo = ProgressionCandidateRepo(driver)

    # Build a lookup of candidate_id → scorecard
    scorecard_lookup: dict[str, dict[str, Any]] = {}
    for sc in state.get("scorecards", []):
        cid = sc.get("candidate_id", "")
        if cid:
            scorecard_lookup[cid] = sc

    saved = 0
    failed = 0
    for candidate_data in state.get("top_progressions", []):
        candidate = ProgressionCandidate.model_validate(candidate_data)

        # Attach scorecard data to candidate metadata so it persists
        sc = scorecard_lookup.get(candidate.id, {})
        candidate.metadata["weighted_total"] = sc.get("weighted_total", 0.0)
        candidate.metadata["scores"] = sc.get("scores", {})

        try:
            await repo.create(candidate)
            saved += 1
        except Neo4jError as e:
            logger.error("Failed to persist candidate %s: %s", candidate.id, e)
            failed += 1
        except Exception:
            logger.exception("Unexpected error persisting candidate %s", candidate.id)
            failed += 1

    if failed > 0:
        logger.warning("Persisted %d/%d candidates (%d failed)", saved, saved + failed, failed)

    if callback:
        top_score = max(
            (s.get("weighted_total", 0.0) for s in state.get("scorecards", [])),
            default=0.0,
        )

        await callback(
            "round_completed",
            {
                "round": state.get("round_number", 1),
                "candidates_count": saved,
                "top_score": round(top_score, 2),
                "stop_met": True,  # M1 is single-round
                "persist_failures": failed,
            },
        )

    return {}
