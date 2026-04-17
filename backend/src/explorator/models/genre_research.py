"""Genre research agent models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)

GenreResearchStatus = Literal[
    "researching",
    "drafting",
    "critiquing",
    "refining",
    "validating",
    "pending_review",
    "approved",
    "rejected",
    "failed",
]

STEP_ORDER = [
    "researching",
    "drafting",
    "critiquing",
    "refining",
    "validating",
    "pending_review",
]


def step_number(status: str) -> int:
    """Derive step number from status string."""
    return STEP_ORDER.index(status) + 1 if status in STEP_ORDER else 0


class CritiqueIssue(BaseModel):
    """A single issue found during critique."""

    severity: Literal["major", "minor"]
    field: str
    suggestion: str


class CritiqueEntry(BaseModel):
    """A single critique/refine iteration."""

    iteration: int
    issues: list[CritiqueIssue] = Field(default_factory=list)
    passed: bool
    resolution: str = ""


class GenreDraftResponse(BaseModel):
    """Structured output from draft and refine steps."""

    profile: GenreProfileYAML
    rules: GenreRulesYAML
    grammar: HarmonicGrammarYAML


class GenreCritiqueResponse(BaseModel):
    """Structured output from critique step."""

    issues: list[CritiqueIssue] = Field(default_factory=list)
    passed: bool


class GenreResearchJob(BaseModel):
    """A genre research job tracked in Neo4j."""

    id: str
    genre_name: str
    reference_artists: list[str] = Field(default_factory=list)
    status: GenreResearchStatus
    research_log: str = ""
    critique_trail: list[CritiqueEntry] = Field(default_factory=list)
    draft_yamls: dict[str, Any] = Field(default_factory=dict)
    rejection_reason: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
