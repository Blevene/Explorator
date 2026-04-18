"""LangGraph node: auto-harvest patterns from finalist arrangements."""
import logging
from typing import Any

from neo4j.exceptions import Neo4jError

from explorator.domain.memory.pattern_harvesting import harvest_finalist
from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo

logger = logging.getLogger(__name__)


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


async def harvest_patterns(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    callback = state.get("on_progress")
    if callback is not None:
        await callback("node_started", {"node": "harvest_patterns"})

    final_selection = state.get("final_selection") or {}
    selected_ids: list[str] = final_selection.get("selected_candidate_ids") or []
    if not selected_ids:
        if callback is not None:
            await callback("node_completed", {"node": "harvest_patterns", "count": 0})
        return {"harvested_pattern_ids": []}

    # Genre is load-bearing for retrieval; harvesting into a sentinel "unknown"
    # genre would pollute the library with unretrievable entries. Skip + warn.
    genre = state.get("genre")
    if not genre:
        logger.warning(
            "harvest_patterns: no genre in state for session %s; skipping harvest",
            state.get("session_id", "?"),
        )
        if callback is not None:
            await callback("node_completed", {"node": "harvest_patterns", "count": 0})
        return {"harvested_pattern_ids": []}

    roles: dict[str, str] = final_selection.get("selection_roles") or {}

    arrangements = _index_by_id(state.get("arrangement_candidates") or [])
    progressions = _index_by_id(state.get("progression_candidates") or [])
    voicing_plans = _index_by_id(state.get("voicing_plans") or [])
    bass_lines = _index_by_id(state.get("bass_lines") or [])
    grooves = _index_by_id(state.get("groove_patterns") or [])
    melodies = _index_by_id(state.get("melodic_complements") or [])
    scorecards_by_cand = {
        s["candidate_id"]: s
        for s in (state.get("scorecards") or [])
        if s.get("candidate_id")
    }

    harvested_ids: list[str] = []
    for arr_id in selected_ids:
        arrangement = arrangements.get(arr_id)
        if arrangement is None:
            continue
        progression = progressions.get(arrangement.get("progression_candidate_id"))
        if progression is None:
            continue
        scorecard = scorecards_by_cand.get(arr_id) or {
            "weighted_total": 0.0, "scores": {}, "pareto_tags": [],
        }
        role = roles.get(arr_id, "unknown")

        entries = harvest_finalist(
            arrangement=arrangement,
            progression=progression,
            voicing_plan=voicing_plans.get(arrangement.get("voicing_plan_id")),
            bass_line=bass_lines.get(arrangement.get("bass_line_id")),
            groove=grooves.get(arrangement.get("groove_pattern_id")),
            melody=melodies.get(arrangement.get("melodic_complement_id")),
            scorecard=scorecard,
            genre=genre,
            role=role,
        )
        # Per-entry try/except: one Neo4j failure doesn't block sibling facets or
        # finalists. The catch is narrowed to Neo4jError so programming errors
        # (KeyError, AttributeError, etc.) surface loudly instead of hiding.
        for entry in entries:
            try:
                await repo.upsert(entry)
                harvested_ids.append(entry.id)
            except Neo4jError as exc:
                logger.error(
                    "harvest_patterns: failed to upsert entry %s (%s/%s): %s",
                    entry.id, entry.pattern_type, entry.source_candidate_id, exc,
                )

    if callback is not None:
        await callback("pattern_harvest", {"count": len(harvested_ids), "genre": genre})
        await callback("node_completed", {"node": "harvest_patterns", "count": len(harvested_ids)})

    return {"harvested_pattern_ids": harvested_ids}
