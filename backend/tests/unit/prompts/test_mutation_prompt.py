"""Tests for mutation prompt generation."""

from explorator.prompts.mutation import mutation_prompt


def test_mutation_prompt_returns_tuple() -> None:
    user, system = mutation_prompt(
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
        genre="dream_pop",
        scores={"genre_fit": 7.0, "novelty": 5.0},
        guidance=None,
        allowed_operations=[
            "substitute_chord", "reharmonize_cadence", "modal_interchange",
            "alter_density", "experimental",
        ],
    )
    assert isinstance(user, str)
    assert isinstance(system, str)
    assert "Cmaj7" in user
    assert "dream_pop" in user


def test_mutation_prompt_includes_guidance() -> None:
    user, _ = mutation_prompt(
        chord_symbols=["Cmaj7", "Am7"],
        genre="synthwave",
        scores={"genre_fit": 6.0},
        guidance="make it darker",
        allowed_operations=["substitute_chord"],
    )
    assert "make it darker" in user
