"""Tests for intent parser service."""

from explorator.domain.intent.parser import extract_deterministic_constraints


def test_extract_key_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Dream pop in A major, wistful and haunted, 8 bars"
    )
    assert constraints["key_center"] == "A"
    assert constraints["mode"] == "major"


def test_extract_bars_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Give me 16 bars of synthwave in C minor"
    )
    assert constraints["phrase_length_bars"] == 16


def test_extract_genre_from_prompt() -> None:
    constraints = extract_deterministic_constraints(
        "Dream pop in A major, 8 bars"
    )
    assert constraints["genre"] == "dream_pop"


def test_extract_mode_minor() -> None:
    constraints = extract_deterministic_constraints(
        "Synthwave in C minor, dark and driving"
    )
    assert constraints["mode"] == "minor"
    assert constraints["key_center"] == "C"


def test_defaults_when_not_specified() -> None:
    constraints = extract_deterministic_constraints(
        "Something dark and moody"
    )
    assert constraints.get("phrase_length_bars") is None
    assert constraints.get("key_center") is None
