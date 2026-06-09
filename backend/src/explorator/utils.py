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
