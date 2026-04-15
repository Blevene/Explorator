"""Deterministic bass line generation from chord symbols."""

from music21 import harmony

from ulid import ULID

from explorator.adapters.music21_adapter import _normalize_chord_symbol
from explorator.models.groove import GroovePattern
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences
from explorator.utils import utc_now

# Bass register octaves: root pitch placed at this octave
_REGISTER_OCTAVE: dict[str, int] = {
    "sub_low": 1,
    "low": 2,
}
_DEFAULT_OCTAVE = 2


def _root_name(chord_symbol: str) -> str:
    """Return the root note name for a chord symbol (e.g. 'C', 'A', 'F').

    Falls back to string extraction if music21 can't parse the chord type.
    """
    normalized = _normalize_chord_symbol(chord_symbol)
    try:
        chord = harmony.ChordSymbol(normalized)
        root = chord.root()
        if root:
            return root.name
    except (ValueError, Exception):
        pass
    # Fallback: extract root from string (e.g. "C13sus4" → "C", "Bb7" → "B-")
    s = normalized.strip()
    if not s:
        return "C"
    if len(s) >= 2 and s[1] in ("-", "b", "#"):
        return s[:2].replace("b", "-")
    return s[0]


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
        groove_pattern: GroovePattern | None = None,
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

        if groove_pattern is not None and groove_pattern.pattern_events:
            return self._groove_driven_events(chord_symbols, prefs, genre, groove_pattern)

        events: list[BassNoteEvent] = []

        for bar_idx, symbol in enumerate(chord_symbols):
            root = _root_name(symbol)

            if mode == "pedal":
                events.extend(
                    self._pedal_events(bar_idx, root, octave, density)
                )
            elif mode == "syncopated":
                events.extend(
                    self._syncopated_events(root, octave, bar_idx)
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

    def _syncopated_events(self, root: str, octave: int, bar: int) -> list[BassNoteEvent]:
        """Syncopated: root on beat 1, root on 'and' of beat 3. Density-independent."""
        pitch = f"{root}{octave}"
        return [
            BassNoteEvent(bar=bar, beat=1.0, duration_beats=1.0, pitch=pitch),
            BassNoteEvent(bar=bar, beat=3.5, duration_beats=0.5, pitch=pitch),
        ]

    def _groove_driven_events(
        self,
        chord_symbols: list[str],
        prefs: BassPreferences,
        genre: str,
        groove: GroovePattern,
    ) -> BassLine:
        """Generate a BassLine driven by a GroovePattern's beat positions.

        For each chord (bar), the groove pattern's events for that bar
        determine timing. Groove events use absolute continuous beats
        (bar 0 = beats 1-4, bar 1 = beats 5-8, etc.), so we filter to
        events belonging to the current bar and convert to per-bar beats.
        Accented beat-1 events use the root; others use the fifth.
        """
        octave = _REGISTER_OCTAVE.get(prefs.default_register, _DEFAULT_OCTAVE)
        events: list[BassNoteEvent] = []

        for bar_idx, symbol in enumerate(chord_symbols):
            root = _root_name(symbol)
            root_pitch = _pitch_with_octave(root, octave)
            fifth_pitch = _fifth_pitch(root, octave)

            # Groove events use absolute beats: bar 0 = 1.0-4.x, bar 1 = 5.0-8.x
            bar_start = bar_idx * 4.0 + 1.0
            bar_end = bar_start + 4.0

            for groove_event in groove.pattern_events:
                if not (bar_start <= groove_event.beat < bar_end):
                    continue
                # Convert absolute beat to per-bar beat (1.0-based)
                per_bar_beat = groove_event.beat - (bar_idx * 4.0)
                if groove_event.accent and per_bar_beat == 1.0:
                    pitch = root_pitch
                else:
                    pitch = fifth_pitch
                events.append(
                    BassNoteEvent(
                        bar=bar_idx,
                        beat=per_bar_beat,
                        duration_beats=groove_event.duration_beats,
                        pitch=pitch,
                        velocity=groove_event.velocity,
                    )
                )

        now = utc_now()
        return BassLine(
            id=f"bl_{ULID()}",
            type="bass_line",
            status="draft",
            created_at=now,
            updated_at=now,
            style_mode="groove_driven",
            contour_type="groove_aligned",
            note_events=events,
        )
