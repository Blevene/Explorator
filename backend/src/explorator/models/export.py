"""Presentation and export models."""

from typing import Any

from pydantic import Field

from explorator.models.base import BaseEntity


class ProvenanceTrace(BaseEntity):
    """Full decision lineage of a session."""

    session_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)


class CandidateExplanation(BaseEntity):
    """Human-readable explanation of one result."""

    candidate_id: str
    summary: str = ""
    why_it_works: list[str] = Field(default_factory=list)
    what_is_experimental: list[str] = Field(default_factory=list)
    recommended_use_cases: list[str] = Field(default_factory=list)


class ComparisonView(BaseEntity):
    """Contrasted presentation set."""

    session_id: str
    candidate_ids: list[str] = Field(default_factory=list)
    comparison_axes: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


class RenderArtifact(BaseEntity):
    """Exported render or file."""

    candidate_id: str
    artifact_type: str
    path: str
    render_metadata: dict[str, Any] = Field(default_factory=dict)


class ExportPackage(BaseEntity):
    """Groups outputs for downstream use."""

    session_id: str
    included_candidate_ids: list[str] = Field(default_factory=list)
    included_artifact_ids: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
