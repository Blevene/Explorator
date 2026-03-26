"""Parse user prompts into structured CreativeBrief.

Uses hybrid approach:
- Deterministic regex extraction for explicit constraints (key, bars, genre)
- Gemini Flash for soft preferences (mood, complexity, aesthetic interpretation)
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.models.session import CreativeBrief
from explorator.utils import utc_now

# Known genres (normalized to snake_case)
KNOWN_GENRES = {
    "dream pop": "dream_pop",
    "dreampop": "dream_pop",
    "synthwave": "synthwave",
    "synth wave": "synthwave",
    "cinematic": "cinematic",
    "film score": "cinematic",
}

# Key pattern: matches "in A major", "in C minor", "in Bb", "in F# minor"
KEY_PATTERN = re.compile(
    r"\bin\s+([A-G][b#]?)\s*(major|minor|maj|min)?\b",
    re.IGNORECASE,
)

# Bars pattern: matches "8 bars", "16 bars", "4-bar"
BARS_PATTERN = re.compile(r"(\d+)\s*[-\s]?bars?", re.IGNORECASE)


class SoftPreferences(BaseModel):
    """LLM-extracted soft preferences from a prompt."""

    mood_targets: list[str] = Field(default_factory=list)
    energy_level: str | None = None
    complexity_target: str = "medium"
    novelty_target: str = "moderate"
    instrumentation_targets: list[str] = Field(default_factory=list)
    user_language_notes: list[str] = Field(default_factory=list)


def extract_deterministic_constraints(prompt: str) -> dict[str, Any]:
    """Extract explicit constraints from prompt using regex."""
    constraints: dict[str, Any] = {}

    # Extract key/mode
    key_match = KEY_PATTERN.search(prompt)
    if key_match:
        constraints["key_center"] = key_match.group(1)
        mode_str = (key_match.group(2) or "").lower()
        if mode_str in ("minor", "min"):
            constraints["mode"] = "minor"
        else:
            constraints["mode"] = "major"

    # Extract bars
    bars_match = BARS_PATTERN.search(prompt)
    if bars_match:
        constraints["phrase_length_bars"] = int(bars_match.group(1))

    # Extract genre
    prompt_lower = prompt.lower()
    for genre_phrase, genre_key in KNOWN_GENRES.items():
        if genre_phrase in prompt_lower:
            constraints["genre"] = genre_key
            break

    return constraints


class IntentParser:
    """Parses user prompts into CreativeBrief using hybrid extraction."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def parse(self, prompt: str, session_id: str) -> CreativeBrief:
        """Parse a prompt into a structured CreativeBrief."""
        # Step 1: Deterministic extraction
        constraints = extract_deterministic_constraints(prompt)

        # Step 2: LLM-assisted soft preference extraction
        soft = await self._extract_soft_preferences(prompt)

        # Step 3: Merge into CreativeBrief
        from ulid import ULID

        brief_id = f"brief_{ULID()}"

        return CreativeBrief(
            id=brief_id,
            type="creative_brief",
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
            genre=constraints.get("genre", "dream_pop"),
            key_center=constraints.get("key_center"),
            mode=constraints.get("mode", "major"),
            phrase_length_bars=constraints.get("phrase_length_bars", 8),
            mood_targets=soft.mood_targets,
            energy_level=soft.energy_level,
            complexity_target=soft.complexity_target,
            novelty_target=soft.novelty_target,
            instrumentation_targets=soft.instrumentation_targets,
            user_language_notes=soft.user_language_notes + [prompt],
        )

    async def _extract_soft_preferences(self, prompt: str) -> SoftPreferences:
        """Use Gemini Flash to extract mood, complexity, and aesthetic preferences."""
        system = (
            "You are a music analysis assistant. Extract soft preferences from "
            "the user's creative prompt. Return structured JSON with mood_targets "
            "(list of mood words), energy_level (low/low_medium/medium/medium_high/high), "
            "complexity_target (low/medium/medium_high/high), novelty_target "
            "(low/moderate/moderate_high/high), instrumentation_targets (list of "
            "instrument names), and user_language_notes (notable phrases from the prompt)."
        )
        try:
            return await self.gemini.generate_structured(
                prompt=f"Extract preferences from this music prompt: {prompt}",
                response_model=SoftPreferences,
                tier=ModelTier.FLASH,
                system_prompt=system,
            )
        except Exception:
            # Fallback: return minimal defaults if Gemini fails
            return SoftPreferences(user_language_notes=[prompt])
