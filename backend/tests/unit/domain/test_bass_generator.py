# backend/tests/unit/domain/test_bass_generator.py

from explorator.domain.realization.bass import BassLineGenerator
from explorator.models.realization import BassLine, BassNoteEvent, BassPreferences


class TestBassLineGeneratorSupportive:
    def test_dream_pop_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="supportive", default_register="low", rhythmic_density="sparse")
        bl = gen.generate(["Cmaj7", "Am7", "Fmaj7", "G7"], prefs, genre="dream_pop")
        assert isinstance(bl, BassLine)
        assert bl.style_mode == "supportive"
        assert len(bl.note_events) == 4  # sparse = one whole note per bar
        assert bl.note_events[0].pitch[0] == "C"  # root of Cmaj7
        assert bl.note_events[1].pitch[0] == "A"  # root of Am7
        assert bl.note_events[0].duration_beats == 4.0

    def test_synthwave_supportive(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="supportive", default_register="low", rhythmic_density="moderate")
        bl = gen.generate(["Cm", "Fm"], prefs, genre="synthwave")
        assert isinstance(bl, BassLine)
        assert len(bl.note_events) == 4  # moderate = root + octave per bar = 2 events × 2 chords

    def test_cinematic_pedal(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="pedal", default_register="low", rhythmic_density="sparse")
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
