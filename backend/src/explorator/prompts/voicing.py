"""Prompts for voicing strategy generation (Gemini Flash)."""


def voicing_strategy_prompt(
    chord_symbols: list[str],
    key_center: str,
    mode: str,
    genre: str,
    voicing_tendencies: dict[str, str],
    voice_count: int,
) -> tuple[str, str]:
    """Build prompt for voicing strategy generation. Returns (user_prompt, system_prompt)."""
    genre_display = genre.replace("_", " ")
    chords = " → ".join(chord_symbols)

    tendencies_text = ""
    if voicing_tendencies:
        items = [f"  - {k}: {v}" for k, v in voicing_tendencies.items()]
        tendencies_text = "Genre voicing tendencies:\n" + "\n".join(items) + "\n\n"

    user_prompt = (
        f"Create a voicing strategy for this {genre_display} chord progression:\n\n"
        f"Progression: {chords}\n"
        f"Key: {key_center} {mode}\n"
        f"Voices: {voice_count}\n\n"
        f"{tendencies_text}"
        "For each chord, specify:\n"
        "- voicing_type: one of 'open', 'close', 'drop2', 'drop3'\n"
        "- target_register: one of 'low', 'mid', 'mid_high', 'high'\n"
        "- extensions_to_include: list of extensions like '7', '9', '13'\n\n"
        "Also provide:\n"
        "- global_strategy: short description of overall voicing approach\n"
        "- density_level: 'thin', 'medium', or 'full'\n"
        f"- voice_count: {voice_count}\n"
    )

    system_prompt = (
        f"You are a music arranger specializing in {genre_display}. "
        f"Create a voicing strategy for a {voice_count}-voice arrangement. "
        "Return valid JSON matching the schema."
    )

    return user_prompt, system_prompt
