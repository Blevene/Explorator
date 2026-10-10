"""Prompts for theory evaluation scoring (the flash-tier LLM)."""


def theory_evaluation_prompt(
    chord_symbols: list[str],
    roman_numerals: str,
    key: str,
    mode: str,
    genre: str,
    mood_targets: list[str],
) -> tuple[str, str]:
    """Build prompt + system prompt for theory evaluation.

    Returns (user_prompt, system_prompt).
    """
    chords = " → ".join(chord_symbols)
    mood = ", ".join(mood_targets) if mood_targets else "not specified"
    genre_display = genre.replace("_", " ")

    user_prompt = (
        "Rate this chord progression on a 0-10 scale. "
        "Be critical and precise. Differentiate between progressions.\n\n"
        f"Progression: {chords}\n"
        f"Roman numerals: {roman_numerals}\n"
        f"Key: {key} {mode}\n"
        f"Target genre: {genre_display}\n"
        f"Target mood: {mood}\n\n"
        "Score (use the FULL 0-10 range, most should be 5-8):\n"
        "- genre_fit: How authentically does this represent the "
        "target genre? Generic = 5-6, authentic = 7-8.\n"
        "- emotional_fit: How well does it match the target mood?\n"
        "- novelty: How creative for the genre? Standard = 3-4, "
        "interesting = 6-7, surprising but coherent = 8+."
    )

    system_prompt = (
        "You are a professional music theory critic. "
        "Score honestly using the full range. "
        "Most progressions should score 5-7, not 8-10."
    )

    return user_prompt, system_prompt
