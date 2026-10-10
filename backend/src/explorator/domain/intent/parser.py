"""Parse user prompts into structured CreativeBrief.

Uses hybrid approach:
- Deterministic regex extraction for explicit constraints (key, bars, genre)
- Gemini Flash for soft preferences (mood, complexity, aesthetic interpretation)
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from explorator.adapters import usage
from explorator.adapters.llm import LLMClient, ModelTier
from explorator.models.session import CreativeBrief
from explorator.prompts.intent import soft_preference_prompt
from explorator.utils import utc_now

logger = logging.getLogger(__name__)

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


# Genre-specific default phrase lengths (when not specified in prompt)
_GENRE_DEFAULT_BARS: dict[str, int] = {
    "dream_pop": 4,       # Dream pop loops are typically short
    "synthwave": 4,       # Synthwave runs on 4-bar loops
    "cinematic": 8,       # Cinematic phrases need more room
}


def _default_bars_for_genre(genre: str) -> int:
    """Return the default phrase length for a genre, or 8 as global fallback."""
    return _GENRE_DEFAULT_BARS.get(genre, 8)


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

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

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
            phrase_length_bars=constraints.get(
                "phrase_length_bars",
                _default_bars_for_genre(constraints.get("genre", "dream_pop")),
            ),
            mood_targets=soft.mood_targets,
            energy_level=soft.energy_level,
            complexity_target=soft.complexity_target,
            novelty_target=soft.novelty_target,
            instrumentation_targets=soft.instrumentation_targets,
            user_language_notes=soft.user_language_notes + [prompt],
        )

    async def _extract_soft_preferences(self, prompt: str) -> SoftPreferences:
        """Use Gemini Flash to extract mood, complexity, and aesthetic preferences."""
        user_prompt, system = soft_preference_prompt(prompt)
        try:
            return await self.llm.generate_structured(
                prompt=user_prompt,
                response_model=SoftPreferences,
                tier=ModelTier.FLASH,
                system_prompt=system,
            )
        except Exception:
            usage.record_fallback("parse_intent")
            logger.warning(
                "Gemini soft preference extraction failed for prompt: %s",
                prompt[:100],
                exc_info=True,
            )
            return SoftPreferences(user_language_notes=[prompt])
