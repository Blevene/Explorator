"""Unit tests for resolve_session_key / resolve_session_mode and
normalize_key_and_mode — explicit key + musical-mode selection.

Key/mode live only in ``metadata.key`` / ``metadata.musical_mode`` (set in
sessions.py). ``musical_mode`` is used (not ``mode``) to avoid colliding with
the session workflow ``mode`` = "full_exploration".
"""

from explorator.utils import (
    normalize_key_and_mode,
    resolve_session_key,
    resolve_session_mode,
)


def test_key_present() -> None:
    assert resolve_session_key({"metadata": {"key": "A"}}) == "A"


def test_key_absent_defaults_c() -> None:
    assert resolve_session_key({"metadata": {"genre": "synthwave"}}) == "C"


def test_key_no_metadata_defaults_c() -> None:
    assert resolve_session_key({}) == "C"


def test_key_empty_string_defaults_c() -> None:
    assert resolve_session_key({"metadata": {"key": ""}}) == "C"


def test_key_metadata_as_json_string() -> None:
    assert resolve_session_key({"metadata": '{"key": "Eb"}'}) == "Eb"


def test_key_non_dict_metadata_defaults_c() -> None:
    assert resolve_session_key({"metadata": "not-json"}) == "C"
    assert resolve_session_key({"metadata": 42}) == "C"


def test_mode_present() -> None:
    assert resolve_session_mode({"metadata": {"musical_mode": "dorian"}}) == "dorian"


def test_mode_absent_defaults_major() -> None:
    assert resolve_session_mode({"metadata": {"key": "A"}}) == "major"


def test_mode_no_metadata_defaults_major() -> None:
    assert resolve_session_mode({}) == "major"


def test_mode_does_not_read_workflow_mode() -> None:
    # The session workflow `mode` must not be confused with the musical mode.
    assert resolve_session_mode({"metadata": {"mode": "full_exploration"}}) == "major"


def test_mode_metadata_as_json_string() -> None:
    assert resolve_session_mode({"metadata": '{"musical_mode": "lydian"}'}) == "lydian"


def test_normalize_passthrough_supported() -> None:
    assert normalize_key_and_mode("A", "dorian") == ("A", "dorian")
    assert normalize_key_and_mode("Eb", "minor") == ("Eb", "minor")


def test_normalize_case_and_accidental() -> None:
    assert normalize_key_and_mode("eb", "DORIAN") == ("Eb", "dorian")
    assert normalize_key_and_mode("f#", "Lydian") == ("F#", "lydian")


def test_normalize_enharmonic_aliases() -> None:
    assert normalize_key_and_mode("Db", "major")[0] == "C#"
    assert normalize_key_and_mode("B-", "major")[0] == "Bb"  # music21 dash-flat in
    assert normalize_key_and_mode("G#", "major")[0] == "Ab"


def test_normalize_falls_back_to_c_major() -> None:
    assert normalize_key_and_mode("H", "klingon") == ("C", "major")
    assert normalize_key_and_mode(None, None) == ("C", "major")
    assert normalize_key_and_mode("", "") == ("C", "major")
