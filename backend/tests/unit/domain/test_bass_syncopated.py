"""Tests for syncopated bass mode in BassLineGenerator."""

from explorator.domain.realization.bass import BassLineGenerator
from explorator.models.realization import BassPreferences


class TestSyncopatedBassMode:
    def test_syncopated_two_events_per_bar(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated", default_register="low")
        bl = gen.generate(["Cm", "Fm"], prefs, genre="synthwave")
        assert bl.style_mode == "syncopated"
        assert len(bl.note_events) == 4  # 2 bars × 2 events

    def test_syncopated_beat_positions(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated")
        bl = gen.generate(["C"], prefs, genre="synthwave")
        assert bl.note_events[0].beat == 1.0
        assert bl.note_events[0].duration_beats == 1.0
        assert bl.note_events[1].beat == 3.5
        assert bl.note_events[1].duration_beats == 0.5

    def test_syncopated_root_notes(self):
        gen = BassLineGenerator()
        prefs = BassPreferences(default_bass_mode="syncopated")
        bl = gen.generate(["Am7", "Dm7"], prefs, genre="synthwave")
        assert bl.note_events[0].pitch.startswith("A")
        assert bl.note_events[2].pitch.startswith("D")

    def test_syncopated_ignores_density(self):
        gen = BassLineGenerator()
        sparse = gen.generate(
            ["C"],
            BassPreferences(default_bass_mode="syncopated", rhythmic_density="sparse"),
            genre="synthwave",
        )
        active = gen.generate(
            ["C"],
            BassPreferences(default_bass_mode="syncopated", rhythmic_density="active"),
            genre="synthwave",
        )
        assert len(sparse.note_events) == len(active.note_events)
