"""Explanation prompts for candidate analysis."""

from __future__ import annotations


def explanation_prompt(
    chord_symbols: list[str],
    roman_numerals: list[str],
    key_center: str,
    mode: str,
    genre: str,
    genre_rules: list[str],
    scores: dict[str, float],
    mutation_lineage: list[str] | None = None,
) -> tuple[str, str]:
    """Build (user_prompt, system_prompt) for candidate explanation.

    Returns a tuple of (user_prompt, system_prompt) strings suitable for
    passing to GeminiClient.generate_structured.
    """
    scores_str = ", ".join(f"{k}={v:.1f}" for k, v in scores.items()) if scores else "none"
    rules_str = "; ".join(genre_rules) if genre_rules else "none specified"

    user_lines = [
        f"Chord progression: {' | '.join(chord_symbols)}",
        f"Roman numeral analysis: {' | '.join(roman_numerals)}",
        f"Key: {key_center} {mode}",
        f"Genre: {genre}",
        f"Genre rules: {rules_str}",
        f"Evaluation scores: {scores_str}",
    ]

    if mutation_lineage:
        user_lines += [
            "",
            f"Mutation history: {', '.join(mutation_lineage)}",
        ]

    user_lines += [
        "",
        "Analyze this chord progression and provide:",
        "- summary: A single sentence describing the character and feel of this progression",
        "- why_it_works: 2-4 bullet points explaining what makes it effective in this genre",
        "- what_is_experimental: 1-3 bullet points about what is unconventional or risky",
        "- recommended_use_cases: 2-3 suggestions for where to use it (intro, verse, bridge, chorus, etc.)",
    ]

    system_prompt = (
        "You are a music theory expert and creative producer specializing in "
        "chord progression analysis. Your explanations should be insightful, "
        "accessible to intermediate musicians, and grounded in both theory and "
        "practical production context. Be specific about harmonic devices "
        "(modal interchange, secondary dominants, tritone substitutions, etc.) "
        "rather than vague. Reference the genre conventions when relevant."
    )

    return "\n".join(user_lines), system_prompt
