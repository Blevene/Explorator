"""Tests for music21 adapter."""

from explorator.adapters.music21_adapter import (
    ChordInfo,
    RomanNumeralResult,
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
