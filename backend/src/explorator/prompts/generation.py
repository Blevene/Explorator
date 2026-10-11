"""Prompts for chord progression generation (the pro-tier LLM)."""


def progression_generation_prompt(
    genre: str,
    key_center: str,
    mode: str,
    bars: int,
    generation_mode: str,
    n_candidates: int,
    harmonic_vocabulary: list[str],
    common_devices: list[str],
    cadence_archetypes: list[str],
    mood_targets: list[str],
) -> tuple[str, str]:
    """Build prompt + system prompt for progression generation.

    Returns (user_prompt, system_prompt).
    """
    mode_instruction = {
        "conservative": (
            "Stay close to genre archetypes. "
            "Prioritize genre fit and familiarity."
        ),
        "balanced": (
            "Mix archetypal progressions with "
            "moderately adventurous options."
        ),
        "exploratory": (
            "Push toward the edges of the genre's boundaries. "
            "Prioritize novelty."
        ),
    }.get(generation_mode, "Mix archetypal and adventurous options.")

    genre_display = genre.replace("_", " ")
    vocab = ", ".join(harmonic_vocabulary) if harmonic_vocabulary else "any"
    devices = ", ".join(common_devices) if common_devices else "none specified"
    cadences = ", ".join(cadence_archetypes) if cadence_archetypes else "any"
    mood = ", ".join(mood_targets) if mood_targets else "not specified"

    user_prompt = (
        "Generate chord progressions for this creative brief:\n\n"
        f"Genre: {genre_display}\n"
        f"Key: {key_center} {mode}\n"
        f"Length: {bars} bars (one chord per bar)\n"
        f"Mood: {mood}\n"
        f"Mode: {generation_mode} — {mode_instruction}\n\n"
        f"Harmonic vocabulary: {vocab}\n"
        f"Common devices: {devices}\n"
        f"Cadence archetypes: {cadences}\n\n"
        "IMPORTANT constraints:\n"
        f"- Exactly {bars} chords (one per bar)\n"
        "- Use standard chord symbols (Cmaj7, Am7, Bbmaj7, Dm9)\n"
        "- Progressions must LOOP well — the last chord should "
        "resolve naturally back to the first\n"
        "- Include a rationale and intent_tags per progression\n\n"
        "Return DISTINCT progressions with varied harmonic approaches."
    )

    system_prompt = (
        f"You are a music theory expert specializing in {genre_display}. "
        f"Generate exactly {n_candidates} distinct chord progressions. "
        "Return valid JSON matching the schema."
    )

    return user_prompt, system_prompt
