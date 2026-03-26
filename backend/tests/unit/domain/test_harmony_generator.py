"""Tests for harmony generator service."""

from explorator.domain.harmony.generator import (
    build_generation_prompt,
)


def test_build_generation_prompt_includes_genre() -> None:
    prompt = build_generation_prompt(
        genre="dream_pop",
        key_center="A",
        mode="major",
        bars=8,
        generation_mode="balanced",
        harmonic_vocabulary=["maj7", "add9", "sus2"],
        common_devices=["borrowed minor iv"],
        cadence_archetypes=["soft_plagal", "open_loop_return"],
        mood_targets=["wistful", "haunted"],
    )
    assert "dream_pop" in prompt or "dream pop" in prompt.lower()
    assert "A major" in prompt or "A" in prompt
    assert "8 bars" in prompt or "8" in prompt
    assert "balanced" in prompt


def test_build_generation_prompt_conservative_mode() -> None:
    prompt = build_generation_prompt(
        genre="synthwave",
        key_center="C",
        mode="minor",
        bars=4,
        generation_mode="conservative",
        harmonic_vocabulary=["minor", "m7"],
        common_devices=["octave bass movement"],
        cadence_archetypes=["minor_plagal"],
        mood_targets=["dark"],
    )
    assert "conservative" in prompt.lower() or "close to archetype" in prompt.lower()
