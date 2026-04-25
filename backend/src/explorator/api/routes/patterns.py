"""Pattern library endpoints: list, get, delete, manual harvest."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import AsyncDriver

from explorator.api.deps import (
    get_harvest_repos,
    get_neo4j_driver,
    get_pattern_library_repo,
    get_session_repo,
)
from explorator.api.schemas.patterns import (
    CurationRequest,
    CurationResponse,
    CursorResponse,
    HarvestReportResponse,
    PatternItem,
    PatternListResponse,
    SkipEntryResponse,
)
from explorator.graph.pattern_library_repo import PatternLibraryRepo
from explorator.graph.session_repo import SessionRepository
from explorator.services.pattern_library.curation_service import (
    ArrangementNotFound,
    PatternsNotHarvested,
    curate_arrangement,
)
from explorator.services.pattern_library.cursor import InvalidCursor, parse_cursor
from explorator.services.pattern_library.filters import PatternFilters
from explorator.services.pattern_library.harvest_service import (
    HarvestRepos,
    harvest_session_finalists,
)

router = APIRouter(tags=["patterns"])


def _to_pattern_item(entry: dict[str, Any]) -> PatternItem:
    """Project a PatternLibraryEntry dict to the public PatternItem schema."""
    return PatternItem(
        id=entry["id"],
        pattern_type=entry["pattern_type"],
        genre=entry["genre"],
        tags=entry.get("tags") or [],
        source_candidate_id=entry["source_candidate_id"],
        abstracted_pattern=entry.get("abstracted_pattern") or {},
        success_metrics=entry.get("success_metrics") or {},
        notes=entry.get("notes") or "",
        created_at=entry["created_at"],
        is_curated=bool(entry.get("is_curated") or False),
        curated_at=entry.get("curated_at"),
    )


@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    genre: str | None = Query(None),
    pattern_type: str | None = Query(None),
    curated_only: bool = Query(False),
    after_score: float | None = Query(None),
    after_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternListResponse:
    try:
        cursor = parse_cursor(after_score, after_id)
    except InvalidCursor as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    items, next_cursor = await repo.list_page(
        filters=PatternFilters(
            genre=genre, pattern_type=pattern_type, curated_only=curated_only,
        ),
        cursor=cursor,
        limit=limit,
    )
    return PatternListResponse(
        items=[_to_pattern_item(e) for e in items],
        next_cursor=(
            CursorResponse(after_score=next_cursor.after_score, after_id=next_cursor.after_id)
            if next_cursor else None
        ),
    )


@router.get("/patterns/{entry_id}", response_model=PatternItem)
async def get_pattern(
    entry_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> PatternItem:
    entry = await repo.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="pattern not found")
    return _to_pattern_item(entry)


@router.delete("/patterns/{entry_id}", status_code=204)
async def delete_pattern(
    entry_id: str,
    repo: PatternLibraryRepo = Depends(get_pattern_library_repo),  # noqa: B008
) -> None:
    ok = await repo.soft_delete(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="pattern not found or already deleted")


@router.post(
    "/sessions/{session_id}/finalists/harvest",
    response_model=HarvestReportResponse,
)
async def harvest_session_finalists_endpoint(
    session_id: str,
    repos: HarvestRepos = Depends(get_harvest_repos),  # noqa: B008
    session_repo: SessionRepository = Depends(get_session_repo),  # noqa: B008
) -> HarvestReportResponse:
    # 404 if session doesn't exist; 200 + upserted_count=0 if session is empty.
    session = await session_repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    report = await harvest_session_finalists(session_id, repos=repos)
    return HarvestReportResponse(
        session_id=report.session_id,
        upserted_count=report.upserted_count,
        skipped_count=report.skipped_count,
        skipped_reasons=[
            SkipEntryResponse(
                candidate_id=e.candidate_id,
                pattern_type=e.pattern_type,
                reason=e.reason.value,
            )
            for e in report.skipped_reasons
        ],
        upserted_pattern_ids=list(report.upserted_pattern_ids),
    )


@router.post(
    "/arrangements/{arrangement_id}/curation",
    response_model=CurationResponse,
)
async def post_curation(
    arrangement_id: str,
    request: CurationRequest,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> CurationResponse:
    try:
        result = await curate_arrangement(
            driver=driver,
            arrangement_id=arrangement_id,
            is_curated=request.curated,
        )
    except ArrangementNotFound as exc:
        raise HTTPException(status_code=404, detail="arrangement not found") from exc
    except PatternsNotHarvested as exc:
        raise HTTPException(
            status_code=409,
            detail="arrangement not yet harvested",
        ) from exc
    return CurationResponse(
        arrangement_id=result.arrangement_id,
        is_curated=result.is_curated,
        curated_at=result.curated_at,
        affected_pattern_ids=result.affected_pattern_ids,
    )
