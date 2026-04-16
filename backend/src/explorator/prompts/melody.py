# backend/src/explorator/prompts/melody.py
"""Prompts for melody strategy generation (Gemini Flash)."""


def melody_strategy_prompt(
    chord_symbols: list[str],
    key_center: str,
    mode: str,
    genre: str,
    melodic_tendencies: dict[str, str],
    voicing_ceiling_notes: list[str],
    bass_floor_notes: list[str],
    groove_summary: str,
) -> tuple[str, str]:
    """Build prompt for melody strategy generation. Returns (user_prompt, system_prompt)."""
    genre_display = genre.replace("_", " ")
    chords = " → ".join(chord_symbols)
    n_bars = len(chord_symbols)

    ceiling = ", ".join(f"bar {i + 1}: {n}" for i, n in enumerate(voicing_ceiling_notes))
    floor = ", ".join(f"bar {i + 1}: {n}" for i, n in enumerate(bass_floor_notes))

    tendencies_text = ""
    if melodic_tendencies:
        items = [f"  - {k}: {v}" for k, v in melodic_tendencies.items()]
        tendencies_text = "Genre melodic tendencies:\n" + "\n".join(items) + "\n\n"

    user_prompt = (
        f"Create a melodic strategy for a single-line melody over this {genre_display} arrangement:\n\n"
        f"Progression ({n_bars} bars): {chords}\n"
        f"Key: {key_center} {mode}\n"
        f"Voicing ceiling (highest note per bar): {ceiling}\n"
        f"Bass floor (lowest note per bar): {floor}\n"
        f"Groove: {groove_summary}\n\n"
        f"{tendencies_text}"
        "Guidelines:\n"
        "- Place melody ABOVE the voicing ceiling to avoid collisions.\n"
        "- Suggest a register range (range_low to range_high) at least a minor 3rd above the voicing ceiling.\n"
        "- Break the melody into phrases (2 or 4 bars each).\n"
        "- For each phrase, specify contour (arch/ascending/descending/wave/static), "
        "density (sparse/moderate/active), strong-beat scale degree targets, "
        "and whether to rest after the phrase.\n"
        "- Provide an overall_contour summary and a one-sentence rationale.\n\n"
        "For each phrase, specify:\n"
        "- start_bar: first bar number (1-indexed)\n"
        "- end_bar: last bar number (inclusive)\n"
        "- contour: one of 'arch', 'ascending', 'descending', 'wave', 'static'\n"
        "- density: one of 'sparse', 'moderate', 'active'\n"
        "- strong_beat_targets: list of scale degree names like 'root', '3rd', '5th', '7th'\n"
        "- rest_after: true/false\n\n"
        "CRITICAL: Keep rationale to ONE sentence (max 200 chars). "
        "Return valid JSON matching the schema.\n"
    )

    system_prompt = (
        f"You are an expert melodist composing a single-line melody over a {genre_display} arrangement. "
        "The melody must stay above the voicing register to avoid pitch collisions. "
        "Create a strategy with phrase-by-phrase instructions that produce a coherent, "
        "genre-appropriate melodic line. Return valid JSON matching the schema."
    )

    return user_prompt, system_prompt
