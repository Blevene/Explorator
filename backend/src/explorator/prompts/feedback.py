"""Feedback interpretation prompt for Gemini Flash."""

from __future__ import annotations

WEIGHT_DIMENSIONS = [
    "genre_fit",
    "emotional_fit",
    "theoretical_coherence",
    "cadence_quality",
    "novelty",
    "loopability",
    "voice_leading",
    "register_density",
    "playability",
]

DIMENSION_DESCRIPTIONS = {
    "genre_fit": "How well the progression fits the target genre conventions",
    "emotional_fit": "Alignment with the requested emotional tone/mood",
    "theoretical_coherence": "Harmonic theory correctness (voice leading rules, functional harmony)",  # noqa: E501
    "cadence_quality": "Strength and appropriateness of cadence points",
    "novelty": "Creative originality and surprise factor",
    "loopability": "How smoothly the progression can loop/repeat",
    "voice_leading": "Smoothness of individual voice movement between chords",
    "register_density": "Balance of note density across pitch registers",
    "playability": "Physical playability on keyboard/guitar",
}


def feedback_interpretation_prompt(
    feedback_text: str,
    current_weights: dict[str, float],
    candidate_scores: dict[str, float],
    genre: str,
) -> tuple[str, str]:
    """Build (user_prompt, system_prompt) for feedback interpretation.

    Returns a tuple of (user_prompt, system_prompt) strings suitable for
    passing to GeminiClient.generate_structured.
    """
    weights_str = "\n".join(
        f"  - {dim}: {current_weights.get(dim, 0.0):.3f} — {DIMENSION_DESCRIPTIONS.get(dim, '')}"
        for dim in WEIGHT_DIMENSIONS
    )

    scores_str = (
        ", ".join(f"{k}={v:.1f}" for k, v in candidate_scores.items())
        if candidate_scores
        else "none available"
    )

    user_prompt = f"""User feedback: "{feedback_text}"

Genre: {genre}
Candidate scores: {scores_str}

Current objective weights (9 dimensions, sum to 1.0):
{weights_str}

Based on the user's feedback:
1. Identify what the user wants changed (interpreted_adjustments).
2. Propose weight_deltas: adjustments to the 9 weight dimensions that reflect the user's preference. Deltas should be small (typically +-0.01 to +-0.05). They must sum to approximately 0.0 (zero-sum) so the total remains ~1.0 after application.
3. Determine if the user is expressing satisfaction with the current result (satisfaction field).

Return interpreted_adjustments (semantic map), weight_deltas (numerical), and satisfaction ("positive", "neutral", or "negative")."""  # noqa: E501

    system_prompt = (
        "You are a music production assistant interpreting user feedback on chord progressions "
        "and arrangements. Translate natural-language preferences into precise scoring weight "
        "adjustments. Be conservative with deltas — small shifts (0.01–0.05) are preferred. "
        "Only mark satisfaction as 'positive' if the user clearly expresses approval "
        '("love this", "perfect", "this is great"). Default to "neutral".'
    )

    return user_prompt, system_prompt
