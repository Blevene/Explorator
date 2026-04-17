"""Output node — persists final state to Neo4j."""

import logging
from typing import Any

from explorator.graph.genre_research_repo import GenreResearchRepository

logger = logging.getLogger(__name__)


async def output_draft(
    state: dict[str, Any],
    *,
    driver: Any,
) -> dict[str, Any]:
    """Persist draft to Neo4j with status pending_review."""
    job_id = state["job_id"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {
        "status": "pending_review",
        "research_log": state.get("research_log", ""),
        "critique_trail": state.get("critique_trail", []),
        "draft_yamls": state.get("draft_yamls", {}),
        "validation_errors": state.get("validation_errors", []),
    })

    if callback:
        await callback("genre_research", {"status": "pending_review", "detail": "Ready for review"})

    return {"status": "pending_review"}
