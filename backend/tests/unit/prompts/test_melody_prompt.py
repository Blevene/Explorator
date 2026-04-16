# backend/tests/unit/prompts/test_melody_prompt.py
"""Tests for melody strategy prompt generation."""

from explorator.prompts.melody import melody_strategy_prompt


class TestMelodyStrategyPrompt:
    def test_returns_user_and_system_prompts(self) -> None:
        user, system = melody_strategy_prompt(
            chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={"motion_preference": "stepwise", "density": "sparse"},
            voicing_ceiling_notes=["B4", "A4", "A4", "B4"],
            bass_floor_notes=["C3", "A2", "F2", "G2"],
            groove_summary="straight eighths, no swing",
        )
        assert isinstance(user, str)
        assert isinstance(system, str)

    def test_user_prompt_contains_chords(self) -> None:
        user, _ = melody_strategy_prompt(
            chord_symbols=["Dm7", "G7"],
            key_center="C",
            mode="major",
            genre="synthwave",
            melodic_tendencies={},
            voicing_ceiling_notes=["A4", "B4"],
            bass_floor_notes=["D3", "G2"],
            groove_summary="moderate density",
        )
        assert "Dm7" in user
        assert "G7" in user
        assert "synthwave" in user.lower() or "Synthwave" in user

    def test_system_prompt_contains_role(self) -> None:
        _, system = melody_strategy_prompt(
            chord_symbols=["Cmaj7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={},
            voicing_ceiling_notes=["B4"],
            bass_floor_notes=["C3"],
            groove_summary="straight eighths",
        )
        assert "melody" in system.lower() or "melodist" in system.lower()

    def test_tendencies_included_when_present(self) -> None:
        user, _ = melody_strategy_prompt(
            chord_symbols=["Cmaj7"],
            key_center="C",
            mode="major",
            genre="dream_pop",
            melodic_tendencies={"motion_preference": "stepwise", "density": "sparse"},
            voicing_ceiling_notes=["B4"],
            bass_floor_notes=["C3"],
            groove_summary="straight eighths",
        )
        assert "stepwise" in user
