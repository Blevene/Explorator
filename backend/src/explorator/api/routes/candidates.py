"""Candidate listing and detail endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel, Field

from explorator.api.deps import get_neo4j_driver
from explorator.graph.repository import BaseRepository
from explorator.utils import parse_json_or_dict

router = APIRouter(tags=["candidates"])


class CandidateRepo(BaseRepository):
    label = "ProgressionCandidate"


class ChordEventResponse(BaseModel):
    bar: int
    beat: float
    duration_beats: float
    symbol: str


class CandidateSummary(BaseModel):
    candidate_id: str
    type: str
    status: str
    key_center: str = ""
    mode: str = ""
    chord_symbols: list[str] = Field(default_factory=list)
    roman_numerals: list[str] = Field(default_factory=list)
    rationale: str = ""
    intent_tags: list[str] = Field(default_factory=list)
    weighted_total: float = 0.0
    scores: dict[str, float] = Field(default_factory=dict)


class CandidateListResponse(BaseModel):
    items: list[CandidateSummary]


def _parse_json_field(value: str | list[object] | None) -> list[object]:
    """Parse a field that may be a JSON string or already a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, TypeError):
            return []
    return []


@router.get("/sessions/{session_id}/candidates")
async def list_candidates(
    session_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> CandidateListResponse:
    """List all progression candidates for a session."""
    repo = CandidateRepo(driver)
    candidates = await repo.query_by_property("session_id", session_id)

    items = []
    for c in candidates:
        chord_events = _parse_json_field(c.get("chord_events"))
        chord_symbols = [e.get("symbol", "") for e in chord_events if isinstance(e, dict)]

        # Parse metadata (may be JSON string from Neo4j)
        metadata = parse_json_or_dict(c.get("metadata"))

        # Extract Roman numeral analysis
        rna = parse_json_or_dict(metadata.get("roman_numeral_analysis"))
        rna_events = rna.get("analysis_events", [])
        roman_numerals = [e.get("symbol", "?") for e in rna_events if isinstance(e, dict)]

        # Extract scores (persisted by persist_round)
        scores_raw = metadata.get("scores", {})
        scores_data = parse_json_or_dict(scores_raw) if isinstance(scores_raw, str) else (
            {k: float(v) for k, v in scores_raw.items()} if isinstance(scores_raw, dict) else {}
        )
        wt = metadata.get("weighted_total", 0.0)
        weighted = float(wt) if wt else 0.0

        items.append(
            CandidateSummary(
                candidate_id=c.get("id", ""),
                type=c.get("type", "progression_candidate"),
                status=c.get("status", "candidate"),
                key_center=c.get("key_center", ""),
                mode=c.get("mode", ""),
                chord_symbols=chord_symbols,
                roman_numerals=roman_numerals,
                rationale=c.get("rationale", ""),
                intent_tags=_parse_json_field(c.get("intent_tags")),
                weighted_total=weighted,
                scores=scores_data,
            )
        )

    return CandidateListResponse(items=items)


@router.get("/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    driver: AsyncDriver = Depends(get_neo4j_driver),  # noqa: B008
) -> CandidateSummary:
    """Get a single candidate by ID."""
    repo = CandidateRepo(driver)
    c = await repo.get_by_id(candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    chord_events = _parse_json_field(c.get("chord_events"))
    chord_symbols = [e.get("symbol", "") for e in chord_events if isinstance(e, dict)]

    return CandidateSummary(
        candidate_id=c.get("id", ""),
        type=c.get("type", "progression_candidate"),
        status=c.get("status", "candidate"),
        key_center=c.get("key_center", ""),
        mode=c.get("mode", ""),
        chord_symbols=chord_symbols,
        rationale=c.get("rationale", ""),
        intent_tags=_parse_json_field(c.get("intent_tags")),
    )
