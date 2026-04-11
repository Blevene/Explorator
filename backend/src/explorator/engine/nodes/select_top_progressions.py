"""Select top progressions node — filter by score + diversity."""

from typing import Any

from explorator.domain.evaluation.ranking import select_top_k
from explorator.engine.state import ExplorationState
from explorator.models.evaluation import AggregateScorecard


async def select_top_progressions(state: ExplorationState) -> dict[str, Any]:
    """Select top K progressions by score."""
    callback = state.get("on_progress")
    if callback:
        await callback("node_started", {"node": "select_top_progressions"})

    scorecards_data = state.get("scorecards", [])
    scorecards = [AggregateScorecard.model_validate(s) for s in scorecards_data]
    k = state.get("k_selection", 4)

    top = select_top_k(scorecards, k)
    top_candidate_ids = {s.candidate_id for s in top}

    # Build scorecard lookup for attaching scores to candidate metadata
    score_lookup = {s.candidate_id: s for s in scorecards}

    # Filter progression candidates to top K and attach M1 scores to metadata
    candidates = state.get("progression_candidates", [])
    top_progressions = []
    for c in candidates:
        if c.get("id") in top_candidate_ids:
            sc = score_lookup.get(c["id"])
            if sc:
                meta = dict(c.get("metadata", {})) if isinstance(c.get("metadata"), dict) else {}
                meta["scores"] = sc.scores
                meta["weighted_total"] = sc.weighted_total
                c = {**c, "metadata": meta}
            top_progressions.append(c)

    if callback:
        await callback(
            "node_completed",
            {"node": "select_top_progressions", "top_count": len(top_progressions)},
        )

    return {"top_progressions": top_progressions}
