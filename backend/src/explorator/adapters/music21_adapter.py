"""Thin music21 adapter for symbolic music analysis.

music21 objects are created transiently and converted to Pydantic types.
No music21 types leak outside this module.
"""

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Map music21 chordKind → clean display suffix for Roman numeral notation
_KIND_TO_SUFFIX: dict[str, str] = {
    "major": "",
    "minor": "",  # case of numeral already indicates minor
    "dominant": "7",
    "major-seventh": "maj7",
    "minor-seventh": "7",  # lowercase numeral + 7 (e.g., ii7)
    "diminished": "dim",
    "diminished-seventh": "dim7",
    "half-diminished": "ø7",
    "augmented": "+",
    "dominant-ninth": "9",
    "major-ninth": "maj9",
    "minor-ninth": "9",
    "suspended-second": "sus2",
    "suspended-fourth": "sus4",
    "power": "5",
    "major-sixth": "6",
    "minor-sixth": "6",
    "dominant-11th": "11",
    "major-minor": "m(maj7)",
    "augmented-seventh": "+7",
}


def _normalize_chord_symbol(symbol: str) -> str:
    """Normalize chord symbols for music21 compatibility.

    music21 uses '-' for flats (e.g., 'B-' not 'Bb'), so we convert
    common flat notation. Handles: Bb, Eb, Ab, Db, Gb.
    """
    import re

    # Replace 'Xb' with 'X-' only at the start (root note), not in quality like 'b5'
    # Match: capital letter + 'b' + (uppercase, digit, or end) — that's a flat root
    return re.sub(r'^([A-G])b(?=[A-Za-z0-9]|$)', r'\1-', symbol)


class ChordInfo(BaseModel):
    """Parsed chord information."""

    root: str
    quality: str
    bass_note: str | None = None
    pitch_classes: list[str] = []


class RomanNumeralResult(BaseModel):
    """Roman numeral analysis for one chord."""

    chord_symbol: str
    roman_numeral: str
    confidence: float = 1.0


def parse_chord_symbol(symbol: str) -> ChordInfo:
    """Parse a chord symbol string into structured info."""
    try:
        from music21 import harmony

        chord = harmony.ChordSymbol(_normalize_chord_symbol(symbol))
        root = chord.root().name if chord.root() else "unknown"
        quality = chord.chordKind or "unknown"
        bass = chord.bass().name if chord.bass() and chord.bass() != chord.root() else None
        pitches = [p.name for p in chord.pitches]

        return ChordInfo(
            root=root,
            quality=quality,
            bass_note=bass,
            pitch_classes=pitches,
        )
    except Exception:
        logger.warning("Failed to parse chord symbol: %s", symbol)
        return ChordInfo(root="unknown", quality="unknown")


def analyze_roman_numerals(
    key: str,
    mode: str,
    chord_symbols: list[str],
) -> list[RomanNumeralResult]:
    """Analyze chord symbols as Roman numerals in a given key.

    Uses music21 for scale degree identification, then applies clean
    quality suffixes instead of figured bass notation.
    """
    from music21 import harmony, roman
    from music21 import key as m21_key

    try:
        analysis_key = m21_key.Key(key, "minor") if mode == "minor" else m21_key.Key(key, "major")
    except Exception:
        logger.warning("Failed to create key: %s %s", key, mode)
        return [
            RomanNumeralResult(chord_symbol=s, roman_numeral="?", confidence=0.0)
            for s in chord_symbols
        ]

    results: list[RomanNumeralResult] = []
    for symbol in chord_symbols:
        try:
            chord = harmony.ChordSymbol(_normalize_chord_symbol(symbol))
            rn = roman.romanNumeralFromChord(chord, analysis_key)

            # Use music21's numeral (handles degree + case correctly)
            # Include front alteration (b, #) for chromatic degrees
            alteration = rn.frontAlterationString or ""
            numeral = f"{alteration}{rn.romanNumeralAlone}"  # e.g., "I", "iv", "bII"
            kind = chord.chordKind or ""
            suffix = _KIND_TO_SUFFIX.get(kind, "")

            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral=f"{numeral}{suffix}",
                    confidence=0.9,
                )
            )
        except Exception:
            # Fallback: try manual degree calculation
            rn_text = _fallback_roman_numeral(symbol, analysis_key)
            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral=rn_text,
                    confidence=0.5 if rn_text != "?" else 0.0,
                )
            )

    return results


# Semitone → (numeral, accidental) for fallback analysis
_MAJOR_DEGREES: dict[int, tuple[str, str]] = {
    0: ("I", ""), 1: ("bII", ""), 2: ("II", ""), 3: ("bIII", ""),
    4: ("III", ""), 5: ("IV", ""), 6: ("bV", ""), 7: ("V", ""),
    8: ("bVI", ""), 9: ("VI", ""), 10: ("bVII", ""), 11: ("VII", ""),
}
_MINOR_DEGREES: dict[int, tuple[str, str]] = {
    0: ("i", ""), 1: ("bII", ""), 2: ("ii", ""), 3: ("III", ""),
    4: ("#III", ""), 5: ("iv", ""), 6: ("bV", ""), 7: ("v", ""),
    8: ("VI", ""), 9: ("#VI", ""), 10: ("VII", ""), 11: ("#VII", ""),
}


# Register bounds: (midi_low, midi_high, center_midi)
_REGISTER_BOUNDS: dict[str, tuple[int, int, int]] = {
    "low":      (36, 60, 48),   # C2–C4, center C3
    "mid":      (48, 72, 60),   # C3–C5, center C4
    "mid_high": (60, 84, 72),   # C4–C6, center C5
    "high":     (72, 96, 84),   # C5–C7, center C6
}

# Extension interval offsets in semitones above root
_EXTENSION_SEMITONES: dict[str, int] = {
    "9":  14,
    "11": 17,
    "13": 21,
}


def realize_voicing(
    symbol: str,
    voicing_type: str,
    register: str,
    voice_count: int,
    extensions: list[str],
) -> list[str]:
    """Convert a chord symbol + voicing parameters into a list of named pitches.

    Parameters
    ----------
    symbol:       Chord symbol string, e.g. "Cmaj7", "Am7", "Bb7"
    voicing_type: One of "close", "open", "drop2", "drop3"
    register:     One of "low", "mid", "mid_high", "high"
    voice_count:  Number of voices to return
    extensions:   List of extension labels to add, e.g. ["9", "11"]

    Returns
    -------
    List of named pitches low-to-high, e.g. ["C3", "G3", "E4", "B4"]
    """
    from music21 import harmony, pitch as m21pitch

    midi_low, midi_high, midi_center = _REGISTER_BOUNDS.get(register, _REGISTER_BOUNDS["mid"])

    # --- 1. Parse chord to get pitch classes (note names, no octave) ---
    chord = harmony.ChordSymbol(_normalize_chord_symbol(symbol))
    base_pitches = chord.pitches  # music21 Pitch objects, arbitrary octave

    # Build ordered list of pitch-class midi values (0-11) with priority weights
    # Priority: root=0 (highest), 3rd/7th=1, 5th=2, extensions=3
    root_pc = chord.root().pitchClass if chord.root() else 0

    # Assign priority to each scale degree position
    pitch_priority: list[tuple[int, int]] = []  # (priority, pitch_class)
    for i, p in enumerate(base_pitches):
        pc = p.pitchClass
        interval = (pc - root_pc) % 12
        if interval == 0:
            pri = 0   # root
        elif interval in (4, 3, 11, 10):
            pri = 1   # 3rd or 7th (major/minor variants)
        elif interval in (7, 6, 8):
            pri = 2   # 5th (perfect, diminished, augmented)
        else:
            pri = 3   # other chord tones
        pitch_priority.append((pri, pc))

    # --- 2. Add extension pitch classes ---
    for ext in extensions:
        semitones = _EXTENSION_SEMITONES.get(str(ext))
        if semitones is not None:
            ext_pc = (root_pc + semitones) % 12
            # Avoid duplicates
            existing_pcs = {pc for _, pc in pitch_priority}
            if ext_pc not in existing_pcs:
                pitch_priority.append((3, ext_pc))

    # --- 3. Select voice_count most important pitch classes ---
    pitch_priority.sort(key=lambda x: x[0])
    selected = pitch_priority[:voice_count]
    selected_pcs = [pc for _, pc in selected]

    # --- 4. Build close-position voicing near register center ---
    # Sort selected pitch classes by ascending interval from root so that
    # close position is always root → 3rd → 5th → 7th (not shuffled by priority tie-breaks).
    root_pc_val = selected_pcs[0] if selected_pcs else 0
    non_root_pcs = sorted(selected_pcs[1:], key=lambda pc: (pc - root_pc_val) % 12)
    selected_pcs = [root_pc_val] + non_root_pcs

    # Find root midi near center
    root_midi = _nearest_midi(root_pc_val, midi_center)

    # Stack remaining voices above root, each as close as possible
    midi_notes = [root_midi]
    current = root_midi
    for pc in selected_pcs[1:]:
        next_midi = _next_midi_above(pc, current)
        midi_notes.append(next_midi)
        current = next_midi

    # --- 5. Apply voicing technique ---
    if voicing_type == "close":
        pass  # already in close position

    elif voicing_type == "open":
        # Spread by dropping every other interior voice down one octave
        if len(midi_notes) >= 3:
            # Drop voices at even indices (1, 3, ...) down an octave
            for i in range(1, len(midi_notes) - 1, 2):
                midi_notes[i] -= 12

    elif voicing_type == "drop2":
        # Drop the second voice from bottom down one octave
        if len(midi_notes) >= 2:
            midi_notes[1] -= 12

    elif voicing_type == "drop3":
        # Drop the third voice from bottom down one octave
        if len(midi_notes) >= 3:
            midi_notes[2] -= 12

    # --- 6. Clamp to register bounds ---
    # Shift the whole voicing by octaves until the centroid falls within bounds.
    # This preserves the relative intervals (important for drop2/drop3).
    midi_notes = _shift_voicing_to_register(midi_notes, midi_low, midi_high)

    # --- 7. Sort low-to-high and return named pitches ---
    midi_notes.sort()
    result = []
    for m in midi_notes:
        p = m21pitch.Pitch()
        p.midi = m
        result.append(p.nameWithOctave)
    return result


def _nearest_midi(pitch_class: int, target_midi: int) -> int:
    """Return the MIDI value for pitch_class closest to target_midi."""
    # Start from octave containing target
    octave = target_midi // 12 - 1  # music21: midi = (octave+1)*12 + pc
    candidate = (octave + 1) * 12 + pitch_class
    # Adjust until closest
    while candidate < target_midi - 6:
        candidate += 12
    while candidate > target_midi + 6:
        candidate -= 12
    return candidate


def _next_midi_above(pitch_class: int, above_midi: int) -> int:
    """Return the nearest MIDI value for pitch_class that is >= above_midi."""
    octave = above_midi // 12 - 1
    candidate = (octave + 1) * 12 + pitch_class
    if candidate < above_midi:
        candidate += 12
    return candidate


def _clamp_to_register(midi: int, low: int, high: int) -> int:
    """Clamp a midi value to [low, high] by octave transposition."""
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    return midi


def _shift_voicing_to_register(midi_notes: list[int], low: int, high: int) -> list[int]:
    """Shift a voicing as a unit by octaves until the centroid is within [low, high].

    Preserves all internal intervals so drop2/drop3 shapes are intact.
    Falls back to per-note clamping only when the span exceeds the register window.
    """
    if not midi_notes:
        return midi_notes

    centroid = sum(midi_notes) / len(midi_notes)

    # Shift up or down by whole octaves until centroid is in range
    while centroid < low:
        midi_notes = [m + 12 for m in midi_notes]
        centroid += 12
    while centroid > high:
        midi_notes = [m - 12 for m in midi_notes]
        centroid -= 12

    return midi_notes


def _fallback_roman_numeral(symbol: str, analysis_key: Any) -> str:
    """Compute Roman numeral manually when music21 fails."""
    try:
        from music21 import harmony, pitch

        chord = harmony.ChordSymbol(_normalize_chord_symbol(symbol))
        root = chord.root()
        if root is None:
            return "?"

        tonic = analysis_key.tonic
        semitones = (pitch.Pitch(root.name).midi - pitch.Pitch(tonic.name).midi) % 12
        table = _MINOR_DEGREES if analysis_key.mode == "minor" else _MAJOR_DEGREES
        numeral, _ = table.get(semitones, ("?", ""))

        kind = chord.chordKind or ""
        suffix = _KIND_TO_SUFFIX.get(kind, "")

        return f"{numeral}{suffix}"
    except Exception:
        return "?"
