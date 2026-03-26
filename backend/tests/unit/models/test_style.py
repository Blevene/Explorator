"""Tests for style domain models."""

from explorator.models.style import AntiPattern, GenreProfile, GenreRule, HarmonicGrammar


def test_genre_profile_creation() -> None:
    profile = GenreProfile(
        id="genre_dream_pop_01",
        type="genre_profile",
        status="active",
        genre="dream_pop",
        display_name="Dream Pop",
        harmonic_vocabulary=["maj7", "add9", "sus2"],
        harmonic_tendencies={
            "functional_strength": "low_medium",
            "chromaticism_level": "moderate",
        },
        voicing_tendencies={"spacing": "open", "register_bias": "mid_high"},
        bass_tendencies={"root_emphasis": "medium"},
        groove_tendencies={"comp_density": "sparse"},
        common_devices=["borrowed minor iv"],
        experimentation_envelope={
            "harmonic_deviation_tolerance": 0.65,
            "voicing_deviation_tolerance": 0.80,
            "groove_deviation_tolerance": 0.40,
        },
    )
    assert profile.genre == "dream_pop"
    assert "maj7" in profile.harmonic_vocabulary


def test_genre_rule_creation() -> None:
    rule = GenreRule(
        id="rule_01",
        type="genre_rule",
        status="active",
        genre="dream_pop",
        rule_type="voicing_preference",
        name="Prefer open voicings",
        description="Spread voicings across mid-high register.",
        weight=0.88,
    )
    assert rule.weight == 0.88
    assert not rule.anti_rule


def test_anti_pattern_creation() -> None:
    ap = AntiPattern(
        id="anti_01",
        type="anti_pattern",
        status="active",
        genre="dream_pop",
        scope="harmony",
        name="Hard bop dominant chains",
        description="Extended ii-V-I sequences break the floating quality.",
        severity=0.85,
    )
    assert ap.severity == 0.85
    assert ap.scope == "harmony"


def test_harmonic_grammar_creation() -> None:
    grammar = HarmonicGrammar(
        id="grammar_01",
        type="harmonic_grammar",
        status="active",
        genre_profile_id="genre_dream_pop_01",
        preferred_chord_qualities=["maj7", "add9", "sus2", "m7"],
        allowed_borrowed_chords=["iv", "bVI", "bVII"],
        cadence_archetypes=["soft_plagal", "open_loop_return"],
    )
    assert "iv" in grammar.allowed_borrowed_chords
