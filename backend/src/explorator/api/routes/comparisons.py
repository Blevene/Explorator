"""Comparison API routes — record comparison events."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.api.deps import get_neo4j_driver
from explorator.graph.comparison_view_repo import ComparisonViewRepo
from explorator.models.export import ComparisonView

logger = logging.getLogger(__name__)
router = APIRouter(tags=["comparisons"])


class ComparisonRequestBody(BaseModel):
    """Request body for recording a comparison event."""

    candidate_ids: list[str]
    comparison_axes: list[str] = []
    labels: dict[str, str] = {}


@router.post("/sessions/{session_id}/comparisons", status_code=201)
async def record_comparison(
    session_id: str,
    body: ComparisonRequestBody,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> dict[str, str]:
    """Record a comparison event for provenance.

    Returns 201 with the comparison_id. Frontend fires this as
    fire-and-forget (.catch logs only, never blocks UI).
    """
    if len(body.candidate_ids) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least 2 candidate_ids required for comparison",
        )

    comparison_id = f"cv_{ULID()}"
    comparison = ComparisonView(
        id=comparison_id,
        type="comparison_view",
        status="active",
        session_id=session_id,
        candidate_ids=body.candidate_ids,
        comparison_axes=body.comparison_axes,
        labels=body.labels,
    )

    repo = ComparisonViewRepo(driver)
    try:
        await repo.create(comparison)

        # Create relationships: (ComparisonView)-[:COMPARES]->(ArrangementCandidate)
        async with driver.session() as neo_session:
            for cid in body.candidate_ids:
                await neo_session.run(
                    """
                    MATCH (cv:ComparisonView {id: $cv_id})
                    MATCH (ac:ArrangementCandidate {id: $ac_id})
                    MERGE (cv)-[:COMPARES]->(ac)
                    """,
                    cv_id=comparison_id,
                    ac_id=cid,
                )
    except Exception:
        logger.exception("Failed to persist comparison view %s", comparison_id)
        raise HTTPException(status_code=500, detail="Failed to record comparison") from None

    return {"comparison_id": comparison_id}
