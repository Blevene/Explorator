from explorator.prompts.voicing import voicing_strategy_prompt


class TestVoicingStrategyPrompt:
    def test_contains_chord_symbols(self):
        user, system = voicing_strategy_prompt(["Cmaj7", "Am7"], "C", "major", "dream_pop", {}, 4)
        assert "Cmaj7" in user
        assert "Am7" in user

    def test_contains_genre(self):
        user, system = voicing_strategy_prompt(["Cm"], "C", "minor", "synthwave", {}, 4)
        assert "synthwave" in user.lower() or "synthwave" in system.lower()

    def test_contains_voice_count(self):
        user, _ = voicing_strategy_prompt(["C"], "C", "major", "dream_pop", {}, 3)
        assert "3" in user

    def test_system_mentions_json(self):
        _, system = voicing_strategy_prompt(["C"], "C", "major", "dream_pop", {}, 4)
        assert "JSON" in system or "json" in system.lower()

    def test_includes_tendencies(self):
        user, _ = voicing_strategy_prompt(["C"], "C", "major", "dream_pop", {"spacing": "open"}, 4)
        assert "spacing" in user
        assert "open" in user
