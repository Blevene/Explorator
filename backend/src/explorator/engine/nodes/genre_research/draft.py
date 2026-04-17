"""Draft node — synthesizes research into structured YAML data using Gemini Flash."""

import json
import logging
from typing import Any

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import GenreDraftResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def draft_yamls(
    state: dict[str, Any],
    *,
    gemini: GeminiClient,
    driver: Any,
) -> dict[str, Any]:
    """Draft three YAML structures from research log."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    research_log = state["research_log"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "drafting"})

    if callback:
        await callback("genre_research", {"status": "drafting", "detail": "Synthesizing research into genre profile..."})

    user_prompt = load_prompt(
        "draft",
        genre_name=genre_name,
        research_log=research_log,
    )
    system_prompt = (
        f"You are a music data engineer creating structured genre data for '{genre_name}'. "
        "Return valid JSON matching the schema exactly."
    )

    # Use generate_text + manual parsing because GenreDraftResponse's nested
    # Pydantic schemas trigger Gemini's "additionalProperties not supported" error
    # when passed as a structured output schema.
    raw_text = await gemini.generate_text(
        prompt=user_prompt,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )

    # Strip markdown code fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    parsed = json.loads(text)

    # Normalize LLM output quirks before Pydantic validation
    # rules: LLM sometimes returns a flat list instead of {"rules": [...], "anti_patterns": [...]}
    if isinstance(parsed.get("rules"), list):
        parsed["rules"] = {"rules": parsed["rules"], "anti_patterns": []}
    # grammar: ensure grammar has genre_profile_id
    if isinstance(parsed.get("grammar"), dict) and "genre_profile_id" not in parsed["grammar"]:
        parsed["grammar"]["genre_profile_id"] = f"genre_{genre_name}_01"

    draft = GenreDraftResponse.model_validate(parsed)

    if callback:
        await callback("genre_research", {"status": "drafting", "detail": "Draft complete"})

    draft_yamls = {
        "profile": draft.profile.model_dump(mode="json"),
        "rules": draft.rules.model_dump(mode="json"),
        "grammar": draft.grammar.model_dump(mode="json"),
    }

    return {"draft_yamls": draft_yamls, "status": "critiquing"}
