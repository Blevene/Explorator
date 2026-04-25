"""Validate node — deterministic Pydantic schema validation."""

import logging
from typing import Any

from explorator.domain.style.schema import (
    GenreProfileYAML,
    GenreRulesYAML,
    HarmonicGrammarYAML,
)
from explorator.graph.genre_research_repo import GenreResearchRepository

logger = logging.getLogger(__name__)

_SCHEMA_MAP = {
    "profile": GenreProfileYAML,
    "rules": GenreRulesYAML,
    "grammar": HarmonicGrammarYAML,
}


def _validate_draft_yamls(draft_yamls: dict[str, Any]) -> list[str]:
    """Validate draft YAMLs against Pydantic schemas. Returns list of error strings."""
    errors: list[str] = []

    # Check top-level keys
    for key in ("profile", "rules", "grammar"):
        if key not in draft_yamls:
            errors.append(f"Missing top-level key: '{key}'")

    if errors:
        return errors

    # Validate each section against its schema
    for key, schema_cls in _SCHEMA_MAP.items():
        try:
            schema_cls.model_validate(draft_yamls[key])
        except Exception as e:
            errors.append(f"Validation error in {key}: {e}")

    # Check experimentation_envelope ranges
    profile = draft_yamls.get("profile", {})
    envelope = profile.get("experimentation_envelope", {})
    for field, value in envelope.items():
        if isinstance(value, (int, float)) and not (0.0 <= value <= 1.0):
            errors.append(f"Envelope value out of range (0-1): {field}={value}")

    # Check rule weights
    rules = draft_yamls.get("rules", {}).get("rules", [])
    for rule in rules:
        weight = rule.get("weight", 0.5)
        if isinstance(weight, (int, float)) and not (0.0 <= weight <= 1.0):
            errors.append(f"Rule weight out of range (0-1): {rule.get('name', '?')}={weight}")

    return errors


async def validate_draft(
    state: dict[str, Any],
    *,
    driver: Any,
) -> dict[str, Any]:
    """Validate draft YAMLs against schemas. Deterministic — no LLM call."""
    job_id = state["job_id"]
    draft_yamls = state["draft_yamls"]
    callback = state.get("on_progress")

    repo = GenreResearchRepository(driver)
    await repo.update_job(job_id, {"status": "validating"})

    if callback:
        await callback(
            "genre_research", {"status": "validating", "detail": "Validating against schemas..."}
        )

    errors = _validate_draft_yamls(draft_yamls)

    if callback:
        if errors:
            await callback(
                "genre_research",
                {"status": "validating", "detail": f"Found {len(errors)} validation warning(s)"},
            )
        else:
            await callback(
                "genre_research", {"status": "validating", "detail": "Validation passed"}
            )

    return {"validation_errors": errors, "status": "pending_review"}
