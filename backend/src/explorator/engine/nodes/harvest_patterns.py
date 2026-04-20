"""LangGraph node: auto-harvest patterns from finalist arrangements.

Thin wrapper around services.pattern_library.harvest_session_finalists_from_state.
Responsibilities kept at this layer:
  1. Emit the three SSE progress events (node_started, pattern_harvest, node_completed)
     with the exact payload shapes M5d-1 established.
  2. Translate HarvestReport → the legacy {"harvested_pattern_ids": [...]} return
     shape expected by existing graph tests.

All orchestration (state indexing, per-finalist loop, repo upsert, error handling)
lives in the service module.
"""
import logging
from typing import Any

from explorator.engine.state import ExplorationState
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.services.pattern_library.harvest_service import (
    harvest_session_finalists_from_state,
)

logger = logging.getLogger(__name__)


async def harvest_patterns(
    state: ExplorationState,
    *,
    repo: PatternLibraryRepo,
) -> dict[str, Any]:
    callback = state.get("on_progress")
    if callback is not None:
        await callback("node_started", {"node": "harvest_patterns"})

    report = await harvest_session_finalists_from_state(
        state, pattern_library_repo=repo,
    )

    # Happy-path domain event: only emitted when something was actually harvested.
    # Preserves M5d-1 semantics (legacy callers observe count + genre keys).
    if callback is not None and report.upserted_count > 0:
        genre = state.get("genre")
        await callback("pattern_harvest", {"count": report.upserted_count, "genre": genre})

    if callback is not None:
        await callback(
            "node_completed",
            {"node": "harvest_patterns", "count": report.upserted_count},
        )

    return {"harvested_pattern_ids": list(report.upserted_pattern_ids)}
