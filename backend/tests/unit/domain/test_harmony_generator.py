"""Tests for harmony generator prompts."""

from explorator.prompts.generation import progression_generation_prompt


def test_generation_prompt_includes_genre() -> None:
    prompt, system = progression_generation_prompt(
        genre="dream_pop",
        key_center="A",
        mode="major",
        bars=8,
        generation_mode="balanced",
        n_candidates=12,
        harmonic_vocabulary=["maj7", "add9", "sus2"],
        common_devices=["borrowed minor iv"],
        cadence_archetypes=["soft_plagal", "open_loop_return"],
        mood_targets=["wistful", "haunted"],
    )
    assert "dream pop" in prompt.lower()
    assert "A" in prompt
    assert "8" in prompt
    assert "balanced" in prompt
    assert "12" in system


def test_generation_prompt_conservative_mode() -> None:
    prompt, system = progression_generation_prompt(
        genre="synthwave",
        key_center="C",
        mode="minor",
        bars=4,
        generation_mode="conservative",
        n_candidates=8,
        harmonic_vocabulary=["minor", "m7"],
        common_devices=["octave bass movement"],
        cadence_archetypes=["minor_plagal"],
        mood_targets=["dark"],
    )
    assert "conservative" in prompt.lower() or "archetype" in prompt.lower()
    assert "LOOP" in prompt
