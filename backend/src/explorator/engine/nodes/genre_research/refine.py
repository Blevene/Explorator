"""Refine node — applies critique to improve draft using Gemini Flash."""

import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import GenreDraftResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def refine_draft(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Refine draft based on critique. Has full context: research + draft + critique."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    research_log = state["research_log"]
    draft_yamls = state["draft_yamls"]
    critique_trail = state.get("critique_trail", [])
    callback = state.get("on_progress")

    # Increment iteration counter FIRST
    iteration = state.get("refine_iteration", 0) + 1

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "refining"})

    if callback:
        await callback("genre_research", {"status": "refining", "detail": f"Refining draft (iteration {iteration}/2)..."})

    # Get the latest critique
    latest_critique = critique_trail[-1] if critique_trail else {}

    user_prompt = load_prompt(
        "refine",
        genre_name=genre_name,
        research_log=research_log,
        draft_yamls=json.dumps(draft_yamls, indent=2),
        critique=json.dumps(latest_critique, indent=2),
    )
    system_prompt = (
        f"You are refining genre data for '{genre_name}' based on reviewer feedback. "
        "Return valid JSON with improved profile, rules, and grammar."
    )

    # Use generate_text + manual parsing to avoid Gemini additionalProperties error
    raw_text = await gemini.generate_text(
        prompt=user_prompt,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()
    parsed = json.loads(text)

    # Normalize LLM output quirks (same as draft node)
    if isinstance(parsed.get("rules"), list):
        parsed["rules"] = {"rules": parsed["rules"], "anti_patterns": []}
    if isinstance(parsed.get("grammar"), dict) and "genre_profile_id" not in parsed["grammar"]:
        parsed["grammar"]["genre_profile_id"] = f"genre_{genre_name}_01"

    refined = GenreDraftResponse.model_validate(parsed)

    if callback:
        await callback("genre_research", {"status": "refining", "detail": "Refinement complete"})

    # Update the resolution on the last critique entry
    trail = list(critique_trail)
    if trail:
        last = dict(trail[-1])
        last["resolution"] = f"Applied {len(last.get('issues', []))} fix(es) in iteration {iteration}"
        trail[-1] = last

    draft_yamls = {
        "profile": refined.profile.model_dump(mode="json"),
        "rules": refined.rules.model_dump(mode="json"),
        "grammar": refined.grammar.model_dump(mode="json"),
    }

    return {
        "draft_yamls": draft_yamls,
        "critique_trail": trail,
        "refine_iteration": iteration,
        "status": "critiquing",
    }
