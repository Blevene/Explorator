"""Draft node — synthesizes research into structured YAML data using the flash-tier LLM."""

import logging
from typing import Any

from explorator.adapters._structured import loads_lenient
from explorator.adapters.llm import LLMClient, ModelTier
from explorator.graph.genre_research_repo import GenreResearchRepository
from explorator.models.genre_research import GenreDraftResponse
from explorator.prompts.genre_research import load_prompt

logger = logging.getLogger(__name__)


def _normalize_draft(parsed: dict[str, Any], genre_name: str) -> None:
    """Normalize common LLM output quirks in-place before Pydantic validation."""
    # rules: LLM sometimes returns a flat list instead of {"rules": [...], "anti_patterns": [...]}
    if isinstance(parsed.get("rules"), list):
        parsed["rules"] = {"rules": parsed["rules"], "anti_patterns": []}
    # Ensure anti_patterns exists
    if isinstance(parsed.get("rules"), dict) and "anti_patterns" not in parsed["rules"]:
        parsed["rules"]["anti_patterns"] = []
    # Identity comes from the validated genre_name, never from the model: a
    # draft claiming another genre would shadow it once approved.
    if isinstance(parsed.get("profile"), dict):
        parsed["profile"]["genre"] = genre_name
    if isinstance(parsed.get("grammar"), dict):
        parsed["grammar"]["genre_profile_id"] = f"genre_{genre_name}_01"
    # Rule applicability: must be dict[str, list[str]]
    rules_data = parsed.get("rules", {})
    for rule in rules_data.get("rules", []):
        applicability = rule.get("applicability", {})
        if isinstance(applicability, str):
            # bare string like "global" or "bassline" → wrap in dict
            rule["applicability"] = {"scope": [applicability]}
        elif isinstance(applicability, dict):
            for key, val in applicability.items():
                if not isinstance(val, list):
                    applicability[key] = [str(val)]
                else:
                    applicability[key] = [str(v) for v in val]
    # Anti-patterns: ensure required fields have defaults
    for ap in rules_data.get("anti_patterns", []):
        if "scope" not in ap:
            ap["scope"] = "general"
        if "severity" not in ap:
            ap["severity"] = 0.5
    # Grammar: harmonic_rhythm_defaults values must be floats, not lists
    grammar = parsed.get("grammar", {})
    hrd = grammar.get("harmonic_rhythm_defaults", {})
    if isinstance(hrd, dict):
        for key, val in hrd.items():
            if isinstance(val, list) and val:
                hrd[key] = float(val[0])  # take first value


async def draft_yamls(
    state: dict[str, Any],
    *,
    llm: LLMClient,
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
        await callback(
            "genre_research",
            {"status": "drafting", "detail": "Synthesizing research into genre profile..."},
        )

    user_prompt = load_prompt(
        "draft",
        genre_name=genre_name,
        research_log=research_log,
    )
    system_prompt = (
        f"You are a music data engineer creating structured genre data for '{genre_name}'. "
        "Return valid JSON matching the schema exactly."
    )

    # generate_text + manual parsing: nested schemas trip Gemini's "additionalProperties" check.
    raw_text = await llm.generate_text(
        prompt=user_prompt,
        tier=ModelTier.FLASH,
        system_prompt=system_prompt,
    )

    parsed = loads_lenient(raw_text)

    _normalize_draft(parsed, genre_name)
    draft = GenreDraftResponse.model_validate(parsed)

    if callback:
        await callback("genre_research", {"status": "drafting", "detail": "Draft complete"})

    draft_yamls = {
        "profile": draft.profile.model_dump(mode="json"),
        "rules": draft.rules.model_dump(mode="json"),
        "grammar": draft.grammar.model_dump(mode="json"),
    }

    return {"draft_yamls": draft_yamls, "status": "critiquing"}
