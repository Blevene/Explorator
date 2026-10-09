"""Critique node — independent review using Gemini Flash with fresh context."""

import json
import logging
from typing import Any

from explorator.adapters._structured import loads_lenient
from explorator.adapters.llm import LLMClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import CritiqueEntry, GenreCritiqueResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def critique_draft(
    state: dict[str, Any],
    *,
    gemini: LLMClient,
    driver: Any,
) -> dict[str, Any]:
    """Critique draft YAMLs. Fresh context — no research log provided."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    draft_yamls = state["draft_yamls"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "critiquing"})

    if callback:
        await callback(
            "genre_research", {"status": "critiquing", "detail": "Reviewing draft for accuracy..."}
        )

    # Fresh context: only draft + genre name, no research log
    user_prompt = load_prompt(
        "critique",
        genre_name=genre_name,
        draft_yamls=json.dumps(draft_yamls, indent=2),
    )
    system_prompt = (
        "You are an independent music theory reviewer. "
        "Assess the genre data objectively without bias. Return valid JSON."
    )

    # generate_text + manual parsing: nested schemas trip Gemini's "additionalProperties" check.
    raw_text = await gemini.generate_text(
        prompt=user_prompt,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )
    parsed = loads_lenient(raw_text)
    critique = GenreCritiqueResponse.model_validate(parsed)

    if callback:
        detail = (
            "No major issues found" if critique.passed else f"Found {len(critique.issues)} issue(s)"
        )
        await callback("genre_research", {"status": "critiquing", "detail": detail})

    # Build critique trail entry
    iteration = state.get("refine_iteration", 0)
    entry = CritiqueEntry(
        iteration=iteration,
        issues=critique.issues,
        passed=critique.passed,
        resolution="",
    )
    trail = list(state.get("critique_trail", []))
    trail.append(entry.model_dump(mode="json"))

    return {
        "critique_trail": trail,
        "needs_refine": not critique.passed,
        "status": "refining" if not critique.passed else "validating",
    }
