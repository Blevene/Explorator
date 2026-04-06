import pytest
from explorator.adapters.music21_adapter import realize_voicing


class TestRealizeVoicingClose:
    def test_major_triad_close_mid(self):
        pitches = realize_voicing("C", "close", "mid", voice_count=3, extensions=[])
        assert len(pitches) == 3
        for p in pitches:
            octave = int(p[-1])
            assert 3 <= octave <= 5  # mid register

    def test_maj7_close_mid_high(self):
        pitches = realize_voicing("Cmaj7", "close", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        pitch_names = [p[:-1] for p in pitches]
        assert "C" in pitch_names
        assert "B" in pitch_names

    def test_minor7_close(self):
        pitches = realize_voicing("Am7", "close", "mid", voice_count=4, extensions=[])
        assert len(pitches) == 4


class TestRealizeVoicingOpen:
    def test_maj7_open_mid_high(self):
        pitches = realize_voicing("Cmaj7", "open", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        from music21 import pitch as m21pitch
        midi_vals = [m21pitch.Pitch(p).midi for p in pitches]
        span = max(midi_vals) - min(midi_vals)
        assert span >= 12  # at least one octave


class TestRealizeVoicingDrop2:
    def test_maj7_drop2(self):
        pitches = realize_voicing("Cmaj7", "drop2", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        from music21 import pitch as m21pitch
        midi_vals = sorted([m21pitch.Pitch(p).midi for p in pitches])
        assert midi_vals[1] - midi_vals[0] >= 8


class TestRealizeVoicingDrop3:
    def test_maj7_drop3(self):
        pitches = realize_voicing("Cmaj7", "drop3", "mid", voice_count=4, extensions=[])
        assert len(pitches) == 4


class TestRealizeVoicingExtensions:
    def test_add9(self):
        pitches = realize_voicing("C", "close", "mid", voice_count=4, extensions=["9"])
        assert len(pitches) == 4
        pitch_names = [p[:-1] for p in pitches]
        assert "D" in pitch_names

    def test_voice_count_limits_output(self):
        pitches = realize_voicing("Cmaj7", "close", "mid", voice_count=3, extensions=["9"])
        assert len(pitches) == 3


class TestRealizeVoicingRegisters:
    def test_low_register(self):
        pitches = realize_voicing("C", "close", "low", voice_count=3, extensions=[])
        from music21 import pitch as m21pitch
        for p in pitches:
            midi = m21pitch.Pitch(p).midi
            assert 36 <= midi <= 72

    def test_high_register(self):
        pitches = realize_voicing("C", "close", "high", voice_count=3, extensions=[])
        from music21 import pitch as m21pitch
        for p in pitches:
            midi = m21pitch.Pitch(p).midi
            assert 72 <= midi <= 108
