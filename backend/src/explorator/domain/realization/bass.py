"""Deterministic bass line generation from chord symbols."""

from music21 import harmony

from ulid import ULID

from explorator.adapters.music21_adapter import _normalize_chord_symbol
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences
from explorator.utils import utc_now

# Bass register octaves: root pitch placed at this octave
_REGISTER_OCTAVE: dict[str, int] = {
    "sub_low": 1,
    "low": 2,
}
_DEFAULT_OCTAVE = 2


def _root_name(chord_symbol: str) -> str:
    """Return the root note name for a chord symbol (e.g. 'C', 'A', 'F')."""
    chord = harmony.ChordSymbol(_normalize_chord_symbol(chord_symbol))
    root = chord.root()
    return root.name if root else "C"


def _pitch_with_octave(note_name: str, octave: int) -> str:
    """Combine a note name and octave into a named pitch string (e.g. 'C2')."""
    return f"{note_name}{octave}"


def _fifth_pitch(root_name: str, octave: int) -> str:
    """Return the pitch a perfect fifth above the root (7 semitones), same octave."""
    from music21 import pitch as m21pitch

    root_midi = m21pitch.Pitch(f"{root_name}{octave}").midi
    fifth_midi = root_midi + 7
    p = m21pitch.Pitch()
    p.midi = fifth_midi
    return p.nameWithOctave


class BassLineGenerator:
    """Generates bass lines from chord symbols using genre-specific templates.

    Purely deterministic — no Gemini calls.
    """

    def generate(
        self,
        chord_symbols: list[str],
        prefs: BassPreferences,
        genre: str = "dream_pop",
    ) -> BassLine:
        """Generate a BassLine for the given chord progression.

        Parameters
        ----------
        chord_symbols:  List of chord symbol strings, one per bar.
        prefs:          BassPreferences specifying mode, register, and density.
        genre:          Genre label (informational; density is driven by prefs).

        Returns
        -------
        A draft BassLine entity.
        """
        octave = _REGISTER_OCTAVE.get(prefs.default_register, _DEFAULT_OCTAVE)
        mode = prefs.default_bass_mode
        density = prefs.rhythmic_density

        events: list[BassNoteEvent] = []

        for bar_idx, symbol in enumerate(chord_symbols):
            root = _root_name(symbol)

            if mode == "pedal":
                events.extend(
                    self._pedal_events(bar_idx, root, octave, density)
                )
            else:
                # "supportive" (default) and everything else
                events.extend(
                    self._supportive_events(bar_idx, root, octave, density)
                )

        now = utc_now()
        return BassLine(
            id=f"bl_{ULID()}",
            type="bass_line",
            status="draft",
            created_at=now,
            updated_at=now,
            style_mode=mode,
            note_events=events,
        )

    # ------------------------------------------------------------------
    # Pattern builders
    # ------------------------------------------------------------------

    def _supportive_events(
        self,
        bar: int,
        root: str,
        octave: int,
        density: str,
    ) -> list[BassNoteEvent]:
        """Return supportive-mode events for one bar."""
        pitch = _pitch_with_octave(root, octave)

        if density == "sparse":
            # One whole note per bar
            return [
                BassNoteEvent(bar=bar, beat=1.0, duration_beats=4.0, pitch=pitch)
            ]
        elif density == "moderate":
            # Root on beat 1 (half note) + octave above on beat 3 (half note)
            octave_pitch = _pitch_with_octave(root, octave + 1)
            return [
                BassNoteEvent(bar=bar, beat=1.0, duration_beats=2.0, pitch=pitch),
                BassNoteEvent(bar=bar, beat=3.0, duration_beats=2.0, pitch=octave_pitch),
            ]
        else:
            # "active": root quarter notes on each beat
            return [
                BassNoteEvent(bar=bar, beat=float(b), duration_beats=1.0, pitch=pitch)
                for b in range(1, 5)
            ]

    def _pedal_events(
        self,
        bar: int,
        root: str,
        octave: int,
        density: str,
    ) -> list[BassNoteEvent]:
        """Return pedal-mode events for one bar.

        sparse: root on beat 1; add 5th on beat 3 every other bar.
        moderate/active: same as supportive but with 5th on beat 3 every other bar.
        """
        pitch = _pitch_with_octave(root, octave)
        fifth = _fifth_pitch(root, octave)

        if density == "sparse":
            events = [BassNoteEvent(bar=bar, beat=1.0, duration_beats=2.0, pitch=pitch)]
            if bar % 2 == 1:
                # Every other bar: add 5th on beat 3
                events.append(
                    BassNoteEvent(bar=bar, beat=3.0, duration_beats=2.0, pitch=fifth)
                )
            else:
                # Even bars: whole-note root
                events[0] = BassNoteEvent(bar=bar, beat=1.0, duration_beats=4.0, pitch=pitch)
            return events
        elif density == "moderate":
            octave_pitch = _pitch_with_octave(root, octave + 1)
            beat3_pitch = fifth if bar % 2 == 1 else octave_pitch
            return [
                BassNoteEvent(bar=bar, beat=1.0, duration_beats=2.0, pitch=pitch),
                BassNoteEvent(bar=bar, beat=3.0, duration_beats=2.0, pitch=beat3_pitch),
            ]
        else:
            # active: quarter notes, replace beat 3 with 5th every other bar
            events = []
            for b in range(1, 5):
                note_pitch = fifth if (b == 3 and bar % 2 == 1) else pitch
                events.append(
                    BassNoteEvent(bar=bar, beat=float(b), duration_beats=1.0, pitch=note_pitch)
                )
            return events
