# backend/tests/unit/domain/test_bass_generator.py

from explorator.domain.realization.bass import BassLineGenerator
from explorator.models.groove import GrooveEvent, GroovePattern
from explorator.models.realization import BassLine, BassPreferences


class TestBassLineGeneratorSupportive:
    def test_dream_pop_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive", default_register="low", rhythmic_density="sparse"
        )
        bl = gen.generate(["Cmaj7", "Am7", "Fmaj7", "G7"], prefs, genre="dream_pop")
        assert isinstance(bl, BassLine)
        assert bl.style_mode == "supportive"
        assert len(bl.note_events) == 4  # sparse = one whole note per bar
        assert bl.note_events[0].pitch[0] == "C"  # root of Cmaj7
        assert bl.note_events[1].pitch[0] == "A"  # root of Am7
        assert bl.note_events[0].duration_beats == 4.0

    def test_synthwave_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive", default_register="low", rhythmic_density="moderate"
        )
        bl = gen.generate(["Cm", "Fm"], prefs, genre="synthwave")
        assert isinstance(bl, BassLine)
        assert len(bl.note_events) == 4  # moderate = root + octave per bar = 2 events × 2 chords

    def test_cinematic_pedal(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="pedal", default_register="low", rhythmic_density="sparse"
        )
        bl = gen.generate(["Cmaj7", "Am7", "Fmaj7", "G7"], prefs, genre="cinematic")
        assert bl.style_mode == "pedal"
        assert len(bl.note_events) >= 4

    def test_bass_register_is_low(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_register="low")
        bl = gen.generate(["C"], prefs, genre="dream_pop")
        octave = int(bl.note_events[0].pitch[-1])
        assert octave <= 3

    def test_entity_fields(self):
        gen = BassLineGenerator()
        prefs = BassPreferences()
        bl = gen.generate(["C"], prefs, genre="dream_pop")
        assert bl.type == "bass_line"
        assert bl.status == "draft"
        assert bl.id.startswith("bl_")


def _make_groove_pattern(events: list[GrooveEvent]) -> GroovePattern:
    """Helper to build a minimal GroovePattern for testing."""
    return GroovePattern(
        id="gp_test",
        type="groove_pattern",
        status="draft",
        session_id="sess_test",
        genre="dream_pop",
        pattern_events=events,
    )


class TestBassLineGeneratorGroove:
    def test_groove_drives_beat_positions(self):
        """A GroovePattern with absolute beat positions should drive bass note timing.

        Groove events use absolute continuous beats: bar 0 = beats 1-4, bar 1 = 5-8.
        """
        gen = BassLineGenerator()
        prefs = BassPreferences(default_register="low")

        # Absolute beats: bar 0 gets 1.0, 3.0; bar 1 gets 5.0, 7.0
        groove = _make_groove_pattern(
            [
                GrooveEvent(beat=1.0, duration_beats=2.0, velocity=100, accent=True),
                GrooveEvent(beat=3.0, duration_beats=2.0, velocity=80, accent=False),
                GrooveEvent(beat=5.0, duration_beats=2.0, velocity=100, accent=True),
                GrooveEvent(beat=7.0, duration_beats=2.0, velocity=80, accent=False),
            ]
        )

        # 2 chords = 2 bars, each bar gets 2 groove events
        bl = gen.generate(["Cmaj7", "Am7"], prefs, genre="dream_pop", groove_pattern=groove)

        assert isinstance(bl, BassLine)
        assert bl.style_mode == "groove_driven"
        assert bl.contour_type == "groove_aligned"
        assert len(bl.note_events) == 4  # 2 chords × 2 groove events

        # Each bar should have a beat-1.0 event (per-bar beats after conversion)
        bar0_events = [e for e in bl.note_events if e.bar == 0]
        bar1_events = [e for e in bl.note_events if e.bar == 1]
        assert any(e.beat == 1.0 for e in bar0_events)
        assert any(e.beat == 1.0 for e in bar1_events)

        # Accented beat-1 events should use the root pitch (C for Cmaj7, A for Am7)
        bar0_beat1 = next(e for e in bar0_events if e.beat == 1.0)
        assert bar0_beat1.pitch.startswith("C")
        bar1_beat1 = next(e for e in bar1_events if e.beat == 1.0)
        assert bar1_beat1.pitch.startswith("A")

    def test_non_accented_events_use_fifth(self):
        """Non-accented groove events should use the fifth rather than the root."""
        gen = BassLineGenerator()
        prefs = BassPreferences(default_register="low")

        groove = _make_groove_pattern(
            [
                GrooveEvent(beat=1.0, duration_beats=2.0, velocity=100, accent=True),
                GrooveEvent(beat=3.0, duration_beats=2.0, velocity=70, accent=False),
            ]
        )

        bl = gen.generate(["C"], prefs, genre="dream_pop", groove_pattern=groove)

        bar0_events = sorted(bl.note_events, key=lambda e: e.beat)
        # beat 1 (accented) = root → starts with C
        assert bar0_events[0].pitch.startswith("C")
        # beat 3 (non-accented) = fifth above C = G
        assert bar0_events[1].pitch.startswith("G")

    def test_no_groove_preserves_existing_behavior(self):
        """Calling generate() without groove_pattern should produce normal BassLine."""
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive", default_register="low", rhythmic_density="sparse"
        )

        bl = gen.generate(["Cmaj7", "Am7", "Fmaj7", "G7"], prefs, genre="dream_pop")

        assert isinstance(bl, BassLine)
        assert bl.style_mode == "supportive"
        # sparse supportive = one whole note per bar
        assert len(bl.note_events) == 4
        assert bl.note_events[0].duration_beats == 4.0

    def test_empty_groove_pattern_falls_back_to_existing(self):
        """A GroovePattern with no events should fall back to normal generation."""
        gen = BassLineGenerator()
        prefs = BassPreferences(
            default_bass_mode="supportive", default_register="low", rhythmic_density="sparse"
        )

        empty_groove = _make_groove_pattern([])
        bl = gen.generate(["C"], prefs, genre="dream_pop", groove_pattern=empty_groove)

        assert bl.style_mode == "supportive"
        assert len(bl.note_events) == 1  # sparse = 1 whole note

    def test_groove_velocity_propagates(self):
        """Groove event velocity should be set on the resulting BassNoteEvent."""
        gen = BassLineGenerator()
        prefs = BassPreferences(default_register="low")

        groove = _make_groove_pattern(
            [
                GrooveEvent(beat=1.0, duration_beats=1.0, velocity=127, accent=True),
            ]
        )

        bl = gen.generate(["C"], prefs, genre="dream_pop", groove_pattern=groove)
        assert bl.note_events[0].velocity == 127
