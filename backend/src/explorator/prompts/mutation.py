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
        "- params: dict with relevant parameters (e.g. position, original, replacement)",
        "- reason: brief explanation",
        "- predicted_effects: dict mapping score names to expected delta (float)",
        "",
        "Return the full mutated chord progression and the list of mutations applied.",
    ]

    system_prompt = (
        "You are an expert music theory assistant specialising in harmonic mutation. "
        "Your task is to apply creative but genre-appropriate mutations to chord progressions. "
        "Always return valid chord symbols. "
        "Keep mutations musically coherent and respect the genre constraints."
    )

    return "\n".join(user_lines), system_prompt
