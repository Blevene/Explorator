"""Thin music21 adapter for symbolic music analysis.

music21 objects are created transiently and converted to Pydantic types.
No music21 types leak outside this module.
"""

import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


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

        chord = harmony.ChordSymbol(symbol)
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
    """Analyze chord symbols as Roman numerals in a given key."""
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
            rn = roman.romanNumeralFromChord(
                _symbol_to_chord(symbol),
                analysis_key,
            )
            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral=rn.romanNumeralAlone + _quality_suffix(rn),
                    confidence=0.9,
                )
            )
        except Exception:
            logger.warning("Failed to analyze %s in %s %s", symbol, key, mode)
            results.append(
                RomanNumeralResult(
                    chord_symbol=symbol,
                    roman_numeral="?",
                    confidence=0.0,
                )
            )

    return results


def _symbol_to_chord(symbol: str):
    """Convert a chord symbol string to a music21 Chord object."""
    from music21 import harmony

    return harmony.ChordSymbol(symbol)


def _quality_suffix(rn) -> str:
    """Extract quality suffix from a Roman numeral object."""
    figure = rn.figure
    numeral = rn.romanNumeralAlone
    # Return everything after the numeral (e.g., "7", "maj7", "m7")
    if figure.startswith(numeral):
        return figure[len(numeral):]
    return ""
