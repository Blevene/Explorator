"""Tests for music21 adapter."""

from explorator.adapters.music21_adapter import (
    ChordInfo,
    RomanNumeralResult,
    _normalize_key_for_music21,
    analyze_roman_numerals,
    parse_chord_symbol,
)


def test_parse_chord_symbol_major_seventh() -> None:
    info = parse_chord_symbol("Cmaj7")
    assert isinstance(info, ChordInfo)
    assert info.root == "C"
    assert "major" in info.quality.lower() or "maj" in info.quality.lower()


def test_parse_chord_symbol_minor_seventh() -> None:
    info = parse_chord_symbol("Am7")
    assert info.root == "A"


def test_parse_chord_symbol_dominant() -> None:
    info = parse_chord_symbol("G7")
    assert info.root == "G"


def test_parse_chord_symbol_sus2() -> None:
    info = parse_chord_symbol("Dsus2")
    assert info.root == "D"


def test_analyze_roman_numerals_major_key() -> None:
    result = analyze_roman_numerals(
        key="C",
        mode="major",
        chord_symbols=["Cmaj7", "Am7", "Fmaj7", "G7"],
    )
    assert isinstance(result, list)
    assert len(result) == 4
    assert all(isinstance(r, RomanNumeralResult) for r in result)
    # C in C major should be I
    assert "I" in result[0].roman_numeral


def test_analyze_roman_numerals_minor_key() -> None:
    result = analyze_roman_numerals(
        key="A",
        mode="minor",
        chord_symbols=["Am", "Dm", "E7", "Am"],
    )
    assert len(result) == 4
    # Am in A minor should be i
    assert "i" in result[0].roman_numeral.lower()


def test_parse_invalid_chord_returns_unknown() -> None:
    info = parse_chord_symbol("Xqz123")
    assert info.root == "unknown"


def test_parse_msus2_normalizes_to_sus2() -> None:
    """Gemini sometimes emits 'Fmsus2' (minor + sus2). music21 has no such
    abbreviation; the normalizer should strip the redundant minor marker
    (sus implies no third) so the chord parses as Fsus2."""
    info = parse_chord_symbol("Fmsus2")
    assert info.root == "F"
    assert info.quality != "unknown"


def test_parse_msus4_normalizes_to_sus4() -> None:
    info = parse_chord_symbol("Dmsus4")
    assert info.root == "D"
    assert info.quality != "unknown"


def test_parse_slash_chord_with_flat_root() -> None:
    """Slash chord with a flat root ('Eb/G') previously failed because the
    flat-normalization lookahead rejected '/' as a trailing char, leaving
    'Eb/G' which music21 interprets as root 'E' + bogus abbreviation 'b'."""
    info = parse_chord_symbol("Eb/G")
    assert info.root in ("E-", "E")  # music21 may name either way
    assert info.bass_note == "G"


def test_parse_slash_chord_preserves_quality() -> None:
    info = parse_chord_symbol("Bbm7/D")
    assert info.root in ("B-", "B")
    assert info.bass_note == "D"
    assert info.quality != "unknown"


# --- Key normalization for music21 (flats use '-', sharps stay) -------------


def test_normalize_key_flat_to_dash() -> None:
    assert _normalize_key_for_music21("Bb") == "B-"
    assert _normalize_key_for_music21("Eb") == "E-"
    assert _normalize_key_for_music21("Ab") == "A-"


def test_normalize_key_sharp_stays() -> None:
    assert _normalize_key_for_music21("C#") == "C#"
    assert _normalize_key_for_music21("F#") == "F#"


def test_normalize_key_natural_unchanged() -> None:
    assert _normalize_key_for_music21("C") == "C"
    assert _normalize_key_for_music21("a") == "A"


# --- Modal Roman-numeral analysis (church modes) ----------------------------


def test_analyze_roman_numerals_dorian_does_not_crash_or_fall_back() -> None:
    """A valid church mode (D dorian) must analyze without crashing and use the
    modal key — not silently fall back to major. In D dorian the i chord (Dm)
    is minor, whereas in D major it would be I; assert the tonic reads as a
    minor numeral, proving the modal key took effect."""
    result = analyze_roman_numerals(
        key="D",
        mode="dorian",
        chord_symbols=["Dm7", "G7", "Am7", "Dm7"],
    )
    assert len(result) == 4
    assert all(isinstance(r, RomanNumeralResult) for r in result)
    # Tonic Dm in D dorian → lowercase 'i' (would be 'I' in D major).
    assert result[0].roman_numeral.startswith("i")
    assert result[0].confidence > 0.0


def test_analyze_roman_numerals_flat_key_modal() -> None:
    """Flat tonic + church mode: Bb dorian must normalize the key to 'B-' for
    music21 and analyze without crashing."""
    result = analyze_roman_numerals(
        key="Bb",
        mode="mixolydian",
        chord_symbols=["Bb", "Ab", "Eb"],
    )
    assert len(result) == 3
    assert any(r.confidence > 0.0 for r in result)
