"""Mutation prompts for harmonic and arrangement operations."""

from __future__ import annotations

MUTATION_OPERATIONS = [
    "substitute_chord",
    "reharmonize_cadence",
    "modal_interchange",
    "alter_density",
    "swap_voicing_type",
    "swap_bass_mode",
    "shift_register",
    "experimental",
]


def mutation_prompt(
    chord_symbols: list[str],
    genre: str,
    scores: dict[str, float],
    guidance: str | None = None,
    allowed_operations: list[str] | None = None,
) -> tuple[str, str]:
    """Build (user_prompt, system_prompt) for harmonic mutation.

    Returns a tuple of (user_prompt, system_prompt) strings suitable for
    passing to GeminiClient.generate_structured.
    """
    ops = allowed_operations or MUTATION_OPERATIONS
    ops_list = ", ".join(ops)

    scores_str = ", ".join(f"{k}={v:.1f}" for k, v in scores.items()) if scores else "none"

    user_lines = [
        f"Chord progression: {' | '.join(chord_symbols)}",
        f"Genre: {genre}",
        f"Current scores: {scores_str}",
    ]

    if guidance:
        user_lines.append(f"User guidance: {guidance}")

    user_lines += [
        "",
        f"Allowed mutation operations: {ops_list}",
        "",
        "Apply 1-3 mutations to improve the progression. For each mutation provide:",
        "- operation: one of the allowed operations",
        "- position: integer index of the chord affected (-1 if not applicable)",
        "- original_value: the chord or value being replaced",
        "- new_value: the replacement chord or value",
        "- description: brief description of the change",
        "- reason: why this mutation should improve the progression",
        "- predicted_score_changes: list of strings like 'novelty: +1.0', 'genre_fit: -0.5'",
        "",
        f"Return mutated_chord_symbols (the COMPLETE mutated progression — must have exactly {len(chord_symbols)} chords, same length as input) and mutations (the list of changes).",  # noqa: E501
        f"CRITICAL: mutated_chord_symbols must contain exactly {len(chord_symbols)} chord symbols. Do NOT truncate or shorten the progression.",  # noqa: E501
    ]

    system_prompt = (
        "You are an expert music theory assistant specialising in harmonic mutation. "
        "Your task is to apply creative but genre-appropriate mutations to chord progressions. "
        "Always return valid chord symbols. "
        "Keep mutations musically coherent and respect the genre constraints."
    )

    return "\n".join(user_lines), system_prompt
