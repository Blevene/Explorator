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
    from music21 import harmony
    from music21 import key as m21_key
    from music21 import roman

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
