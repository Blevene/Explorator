from explorator.prompts.feedback import feedback_interpretation_prompt

WEIGHT_DIMENSIONS = [
    "genre_fit", "emotional_fit", "theoretical_coherence",
    "cadence_quality", "novelty", "loopability",
    "voice_leading", "register_density", "playability",
]


def test_prompt_includes_feedback_text() -> None:
    user_prompt, system_prompt = feedback_interpretation_prompt(
        feedback_text="bass is too busy, prefer open voicings",
        current_weights={"genre_fit": 0.15, "novelty": 0.10},
        candidate_scores={"genre_fit": 7.0, "novelty": 6.5},
        genre="dream_pop",
    )
    assert "bass is too busy" in user_prompt
    assert "dream_pop" in user_prompt
    assert system_prompt  # non-empty


def test_prompt_includes_current_weights() -> None:
    user_prompt, _ = feedback_interpretation_prompt(
        feedback_text="more experimental",
        current_weights={"novelty": 0.10, "genre_fit": 0.15},
        candidate_scores={},
        genre="lo_fi_hip_hop",
    )
    assert "novelty" in user_prompt
    assert "0.10" in user_prompt or "0.1" in user_prompt


def test_prompt_lists_all_weight_dimensions() -> None:
    user_prompt, _ = feedback_interpretation_prompt(
        feedback_text="test",
        current_weights={dim: round(1.0 / 9, 3) for dim in WEIGHT_DIMENSIONS},
        candidate_scores={},
        genre="jazz",
    )
    for dim in WEIGHT_DIMENSIONS:
        assert dim in user_prompt
