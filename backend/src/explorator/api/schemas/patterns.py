"""API schemas for the pattern library endpoints."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PatternItem(BaseModel):
    """Public-facing projection of PatternLibraryEntry.

    Drops `embedding` (large, useless in browser) and `deleted_at` (404 masks it).
    """
    id: str
    pattern_type: str
    genre: str
    tags: list[str] = Field(default_factory=list)
    source_candidate_id: str
    abstracted_pattern: dict[str, Any] = Field(default_factory=dict)
    success_metrics: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
    created_at: datetime
    is_curated: bool = False
    curated_at: datetime | None = None


class CursorResponse(BaseModel):
    after_score: float
    after_id: str


class PatternListResponse(BaseModel):
    items: list[PatternItem]
    next_cursor: CursorResponse | None = None


class SkipEntryResponse(BaseModel):
    candidate_id: str
    pattern_type: str
    reason: str  # serialized SkipReason value


class HarvestReportResponse(BaseModel):
    session_id: str
    upserted_count: int
    skipped_count: int
    skipped_reasons: list[SkipEntryResponse] = Field(default_factory=list)
    upserted_pattern_ids: list[str] = Field(default_factory=list)


class CurationRequest(BaseModel):
    curated: bool


class CurationResponse(BaseModel):
    arrangement_id: str
    is_curated: bool
    curated_at: datetime | None = None
    affected_pattern_ids: list[str] = Field(default_factory=list)
