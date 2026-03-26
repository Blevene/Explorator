"""Shared base interfaces for all domain entities."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from explorator.utils import utc_now


class BaseEntity(BaseModel):
    """Base interface for all persistent domain entities."""

    id: str
    type: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    version: int = 1
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateBase(BaseEntity):
    """Shared interface for ProgressionCandidate and ArrangementCandidate."""

    session_id: str
    family_id: str | None = None
    intent_tags: list[str] = Field(default_factory=list)
    rationale: str
    mutation_lineage_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvaluationBase(BaseEntity):
    """Shared interface for all evaluation types."""

    candidate_id: str
    evaluation_type: str
    notes: list[str] = Field(default_factory=list)
