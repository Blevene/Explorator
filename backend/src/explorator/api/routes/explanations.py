"""Explanation API routes — generate and cache candidate explanations."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel
from ulid import ULID

from explorator.adapters.llm import LLMClient, ModelTier
from explorator.api.deps import get_llm_client, get_neo4j_driver
from explorator.models.export import CandidateExplanation
from explorator.persistence.factory import (
    make_arrangement_candidate_repo,
    make_candidate_explanation_repo,
    make_candidate_repo,
    make_session_repo,
)
from explorator.prompts.explanation import explanation_prompt
from explorator.utils import parse_json_or_dict, resolve_session_genre

logger = logging.getLogger(__name__)
router = APIRouter(tags=["explanations"])


class ExplanationResponse(BaseModel):
    """Structured explanation of a candidate."""

    summary: str
    why_it_works: list[str]
    what_is_experimental: list[str]
    recommended_use_cases: list[str]


class GeminiExplanationOutput(BaseModel):
    """Schema for Gemini structured output."""

    summary: str
    why_it_works: list[str]
    what_is_experimental: list[str]
    recommended_use_cases: list[str]


@router.get("/candidates/{candidate_id}/explanation")
async def get_explanation(
    candidate_id: str,
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
) -> ExplanationResponse:
    """Get a cached explanation for a candidate (404 if not generated)."""
    repo = make_candidate_explanation_repo(driver)
    cached = await repo.get_by_candidate_id(candidate_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Explanation not generated yet")
    return ExplanationResponse(
        summary=cached.get("summary", ""),
        why_it_works=cached.get("why_it_works", []),
        what_is_experimental=cached.get("what_is_experimental", []),
        recommended_use_cases=cached.get("recommended_use_cases", []),
    )


@router.post("/candidates/{candidate_id}/explain")
async def generate_or_get_explanation(
    candidate_id: str,
    driver: AsyncDriver | None = Depends(get_neo4j_driver),  # noqa: B008
    llm: LLMClient = Depends(get_llm_client),  # noqa: B008
) -> ExplanationResponse:
    """Generate or return cached explanation for a candidate.

    Checks the cache first. If not found, loads context, calls Gemini Pro,
    persists (no-op in memory mode), and returns.
    """
    explanation_repo = make_candidate_explanation_repo(driver)

    # Check cache
    cached = await explanation_repo.get_by_candidate_id(candidate_id)
    if cached is not None:
        return ExplanationResponse(
            summary=cached.get("summary", ""),
            why_it_works=cached.get("why_it_works", []),
            what_is_experimental=cached.get("what_is_experimental", []),
            recommended_use_cases=cached.get("recommended_use_cases", []),
        )

    # Load ArrangementCandidate
    ac_repo = make_arrangement_candidate_repo(driver)
    ac_data = await ac_repo.get_by_id(candidate_id)
    if ac_data is None:
        raise HTTPException(status_code=404, detail="ArrangementCandidate not found")

    # Load parent ProgressionCandidate
    prog_id = ac_data.get("progression_candidate_id", "")
    prog_repo = make_candidate_repo(driver)
    prog_data = await prog_repo.get_by_id(prog_id) if prog_id else None
    if prog_data is None:
        raise HTTPException(
            status_code=422,
            detail=f"ProgressionCandidate not found for arrangement {candidate_id}",
        )

    session_id = ac_data.get("session_id", prog_data.get("session_id", ""))

    # Extract data
    chord_symbols = prog_data.get("chord_symbols", [])
    roman_numerals = prog_data.get("roman_numerals", [])
    key_center = prog_data.get("key_center", "C")
    mode = prog_data.get("mode", "major")
    prog_meta = parse_json_or_dict(prog_data.get("metadata", {}))
    genre = prog_meta.get("genre", prog_data.get("genre", ""))
    # Candidate metadata carries no genre in memory mode; fall back to the
    # session's genre (single source of truth) so the explanation prompt and
    # genre-rule lookup run under the correct genre.
    if not genre and session_id:
        session = await make_session_repo(driver).get_by_id(session_id)
        if session is not None:
            genre = resolve_session_genre(session)

    # Scores from arrangement metadata/scorecard
    ac_meta = parse_json_or_dict(ac_data.get("metadata", {}))
    scores: dict[str, float] = ac_meta.get("scores", {})
    if not scores:
        scores = prog_meta.get("scores", {})

    # Genre rules (Neo4j-only; absent in memory mode → empty context).
    genre_rules: list[str] = []
    if genre and driver is not None:
        async with driver.session() as neo_session:
            result = await neo_session.run(
                "MATCH (r:GenreRule {genre: $genre}) RETURN r",
                genre=genre,
            )
            genre_rules = [
                desc
                async for record in result
                if (desc := dict(record["r"]).get("description"))
            ]

    # Mutation lineage
    mutation_lineage: list[str] | None = None
    mutation_ops = prog_meta.get("mutation_ops", [])
    if mutation_ops:
        mutation_lineage = [
            op.get("description", f"{op.get('operation', '?')}")
            for op in mutation_ops
        ]

    # Build prompt and call Gemini Pro
    user_prompt, system_prompt = explanation_prompt(
        chord_symbols=chord_symbols,
        roman_numerals=roman_numerals,
        key_center=key_center,
        mode=mode,
        genre=genre,
        genre_rules=genre_rules,
        scores=scores,
        mutation_lineage=mutation_lineage,
    )

    try:
        llm_result = await llm.generate_structured(
            user_prompt,
            GeminiExplanationOutput,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.exception("Gemini explanation generation failed for %s", candidate_id)
        raise HTTPException(
            status_code=504,
            detail="Explanation generation timed out. Try again.",
        ) from exc

    # Persist to Neo4j
    explanation = CandidateExplanation(
        id=f"ce_{ULID()}",
        type="candidate_explanation",
        status="active",
        session_id=session_id,
        candidate_id=candidate_id,
        summary=llm_result.summary,
        why_it_works=llm_result.why_it_works,
        what_is_experimental=llm_result.what_is_experimental,
        recommended_use_cases=llm_result.recommended_use_cases,
    )
    try:
        await explanation_repo.create(explanation)

        # Create relationship: (CandidateExplanation)-[:EXPLAINS]->(ArrangementCandidate).
        # Neo4j-only; skipped (and create is a no-op) in memory mode.
        if driver is not None:
            async with driver.session() as neo_session:
                await neo_session.run(
                    """
                    MATCH (e:CandidateExplanation {id: $eid})
                    MATCH (a:ArrangementCandidate {id: $aid})
                    MERGE (e)-[:EXPLAINS]->(a)
                    """,
                    eid=explanation.id,
                    aid=candidate_id,
                )
    except Exception:
        logger.exception("Failed to persist explanation for %s", candidate_id)
        # Still return the result even if persistence fails

    return ExplanationResponse(
        summary=llm_result.summary,
        why_it_works=llm_result.why_it_works,
        what_is_experimental=llm_result.what_is_experimental,
        recommended_use_cases=llm_result.recommended_use_cases,
    )
