"""Tests for explanation prompt generation."""

import pytest

from explorator.prompts.explanation import explanation_prompt


class TestExplanationPrompt:
    """Verify explanation_prompt returns (user_prompt, system_prompt) tuple."""

    def test_returns_tuple(self):
        result = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=["Use extended chords", "Avoid power chords"],
            scores={"voice_leading": 8.5, "tension_curve": 7.2, "playability": 9.0},
            mutation_lineage=None,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_user_prompt_contains_chords(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            roman_numerals=["Imaj7", "vim7", "IVmaj7", "V7"],
            key_center="C",
            mode="major",
            genre="synthwave",
            genre_rules=[],
            scores={"voice_leading": 8.0},
            mutation_lineage=None,
        )
        assert "Cmaj7" in user_prompt
        assert "synthwave" in user_prompt
        assert "voice_leading" in user_prompt

    def test_user_prompt_contains_roman_numerals(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Cmaj7", "Am7"],
            roman_numerals=["Imaj7", "vim7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert "Imaj7" in user_prompt

    def test_user_prompt_includes_mutation_lineage(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["Dm7", "G7", "Cmaj7", "Am7"],
            roman_numerals=["iim7", "V7", "Imaj7", "vim7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={"voice_leading": 7.0},
            mutation_lineage=["reharmonize bar 3", "smooth voice leading"],
        )
        assert "reharmonize bar 3" in user_prompt
        assert "smooth voice leading" in user_prompt

    def test_user_prompt_omits_lineage_when_none(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["C", "Am"],
            roman_numerals=["I", "vi"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert "mutation" not in user_prompt.lower() or "lineage" not in user_prompt.lower()

    def test_system_prompt_is_nonempty(self):
        _, system_prompt = explanation_prompt(
            chord_symbols=["C"],
            roman_numerals=["I"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            genre_rules=[],
            scores={},
            mutation_lineage=None,
        )
        assert len(system_prompt) > 20

    def test_genre_rules_included(self):
        user_prompt, _ = explanation_prompt(
            chord_symbols=["C"],
            roman_numerals=["I"],
            key_center="C",
            mode="major",
            genre="synthwave",
            genre_rules=["Use seventh chords", "Prefer minor keys"],
            scores={},
            mutation_lineage=None,
        )
        assert "Use seventh chords" in user_prompt
        assert "Prefer minor keys" in user_prompt
