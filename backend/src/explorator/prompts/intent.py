"""Prompts for intent parsing (Gemini Flash)."""


SOFT_PREFERENCE_SYSTEM = (
    "You are a music analysis assistant. Extract soft preferences from "
    "the user's creative prompt. Return structured JSON with mood_targets "
    "(list of mood words), energy_level "
    "(low/low_medium/medium/medium_high/high), "
    "complexity_target (low/medium/medium_high/high), novelty_target "
    "(low/moderate/moderate_high/high), instrumentation_targets (list of "
    "instrument names), and user_language_notes "
    "(notable phrases from the prompt)."
)


def soft_preference_prompt(user_prompt: str) -> tuple[str, str]:
    """Build prompt for extracting soft preferences.

    Returns (user_prompt, system_prompt).
    """
    return (
        f"Extract preferences from this music prompt: {user_prompt}",
        SOFT_PREFERENCE_SYSTEM,
    )
