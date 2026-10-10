"""Research node — uses Gemini Pro to research a genre."""

import logging
from typing import Any

from explorator.adapters.llm import LLMClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


async def research_genre(
    state: dict[str, Any],
    *,
    llm: LLMClient,
    driver: Any,
) -> dict[str, Any]:
    """Research a genre using Gemini Pro. Returns research_log."""
    job_id = state["job_id"]
    genre_name = state["genre_name"]
    reference_artists = state.get("reference_artists", [])
    callback = state.get("on_progress")

    # Update Neo4j status
    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "researching"})

    # Build reference artists section
    if reference_artists:
        artists_text = (
            "## Reference Artists\n"
            "Use these artists as style anchors:\n"
            + "\n".join(f"- {a}" for a in reference_artists)
            + "\n"
        )
    else:
        artists_text = ""

    # Build prompt
    user_prompt = load_prompt(
        "research",
        genre_name=genre_name,
        reference_artists_section=artists_text,
    )
    system_prompt = (
        f"You are an expert musicologist researching the genre '{genre_name}' "
        "for a music generation system. Be thorough and specific."
    )

    if callback:
        await callback(
            "genre_research",
            {"status": "researching", "detail": "Researching harmonic vocabulary..."},
        )

    research_log = await llm.generate_text(
        prompt=user_prompt,
        tier=ModelTier.PRO,
        system_prompt=system_prompt,
    )

    if callback:
        await callback("genre_research", {"status": "researching", "detail": "Research complete"})

    return {"research_log": research_log, "status": "drafting"}
