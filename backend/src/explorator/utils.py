"""Shared utility functions."""

import json
import re
from datetime import UTC, datetime
from typing import Any

_NOTE_SEMITONES = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_PITCH_RE_DASH_FLAT = re.compile(r"^([A-Ga-g])(-)(\d+)$")


def _midi_from_parts(note: str, accidental: str, octave_str: str) -> int:
    base = _NOTE_SEMITONES[note.upper()]
    midi = (int(octave_str) + 1) * 12 + base
    if accidental == "#":
        midi += 1
    elif accidental in ("b", "-"):
        midi -= 1
    return midi


def pitch_str_to_midi(pitch: str) -> int:
    """Convert pitch string to MIDI note number. Pure Python, no music21.

    Handles: "C4" → 60, "F#4" → 66, "Bb3" → 58, "B-3" → 58 (music21 format),
    "C-1" → 0 (C in octave -1, the lowest MIDI note).
    Raises ValueError for unparseable input.
    """
    s = pitch.strip()
    if not s:
        raise ValueError(f"Cannot parse pitch string: {pitch!r}")

    # Standard form: note + optional #/b + signed octave (covers "C4", "F#4", "Bb3", "C-1")
    m = _PITCH_RE.match(s)
    if m:
        note, acc, oct_str = m.groups()
        midi = _midi_from_parts(note, acc, oct_str)
        if 0 <= midi <= 127:
            return midi
        # Out of range with standard parse — try dash-as-flat (music21 "B-3", "E-4")
        m2 = _PITCH_RE_DASH_FLAT.match(s)
        if m2:
            midi2 = _midi_from_parts(*m2.groups())
            if 0 <= midi2 <= 127:
                return midi2

    raise ValueError(f"Cannot parse pitch string: {pitch!r}")


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def parse_json_field(data: dict[str, Any], field: str) -> Any:
    """Parse a JSON string field if stored as a string; return as-is otherwise.

    Used for Neo4j properties that may be serialized as JSON strings.
    """
    value = data.get(field)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    return value


def parse_json_or_dict(value: Any) -> dict[str, Any]:
    """Parse a value that may be a JSON string, dict, or None into a dict.

    Used for Neo4j properties that store dicts as JSON strings.
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def resolve_session_genre(session: dict[str, Any]) -> str:
    """Resolve a session's genre from its ``metadata`` (single source of truth).

    Genre is persisted only in ``metadata.genre`` (set in sessions.py); the
    ``Session`` model has no top-level ``genre`` field. In memory mode neither
    a ``Session.genre`` property nor a CreativeBrief is written, so this is the
    only reliable genre source. Falls back to ``"dream_pop"`` when absent.
    """
    return parse_json_or_dict(session.get("metadata")).get("genre") or "dream_pop"


# --- Key + musical-mode selection -------------------------------------------
# Explicit key/mode are threaded through generation like genre. They are
# persisted in ``metadata.key`` / ``metadata.musical_mode`` (the latter avoids
# colliding with the session workflow ``mode`` = "full_exploration"). These map
# to the generator's ``key_center`` / ``mode`` params and ``CreativeBrief``.

DEFAULT_KEY = "C"
DEFAULT_MODE = "major"

# Canonical key spellings the frontend sends (12 pitch classes).
SUPPORTED_KEYS = {"C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"}

# Supported musical modes (major/minor + the five common church modes).
SUPPORTED_MODES = {
    "major",
    "minor",
    "dorian",
    "phrygian",
    "lydian",
    "mixolydian",
    "locrian",
}

# Enharmonic / formatting aliases → canonical key spelling. Accepts music21's
# dash-flat form, lowercase, and a few common enharmonic spellings so a value
# coming from anywhere normalizes cleanly instead of falling back to C.
_KEY_ALIASES = {
    "DB": "C#",
    "C#": "C#",
    "D#": "Eb",
    "E-": "Eb",
    "EB": "Eb",
    "GB": "F#",
    "F#": "F#",
    "G#": "Ab",
    "A-": "Ab",
    "AB": "Ab",
    "A#": "Bb",
    "B-": "Bb",
    "BB": "Bb",
    "C-": "B",
    "F-": "E",
    "E#": "F",
    "B#": "C",
}


def normalize_key_and_mode(key: str | None, musical_mode: str | None) -> tuple[str, str]:
    """Normalize an arbitrary key + musical mode to a supported pair.

    All 12 keys x 7 modes are valid — this normalizes (case, enharmonic,
    dash-flat) rather than rejecting, and falls back to C/major for anything
    unrecognized so a bad value can never crash generation. Used at the route
    boundary.
    """
    raw_key = (key or "").strip()
    if raw_key:
        # Canonicalize accidental case: 'eb' → 'Eb', 'f#' → 'F#'.
        if len(raw_key) > 1:
            canon = raw_key[0].upper() + raw_key[1:].replace("B", "b")
        else:
            canon = raw_key.upper()
        if canon in SUPPORTED_KEYS:
            norm_key = canon
        else:
            norm_key = _KEY_ALIASES.get(raw_key.upper(), DEFAULT_KEY)
    else:
        norm_key = DEFAULT_KEY

    raw_mode = (musical_mode or "").strip().lower()
    norm_mode = raw_mode if raw_mode in SUPPORTED_MODES else DEFAULT_MODE
    return norm_key, norm_mode


def resolve_session_key(session: dict[str, Any]) -> str:
    """Resolve a session's key from its ``metadata.key`` (default ``"C"``)."""
    return parse_json_or_dict(session.get("metadata")).get("key") or DEFAULT_KEY


def resolve_session_mode(session: dict[str, Any]) -> str:
    """Resolve a session's musical mode from ``metadata.musical_mode``.

    Defaults to ``"major"``. Reads ``musical_mode`` (not ``mode``) to avoid
    colliding with the session workflow ``mode``.
    """
    return parse_json_or_dict(session.get("metadata")).get("musical_mode") or DEFAULT_MODE
