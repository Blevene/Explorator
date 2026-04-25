from explorator.adapters.music21_adapter import check_voice_leading, realize_voicing
from explorator.models.realization import VoiceLeadingCheck


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
        """Drop-2 drops the 2nd voice from top down an octave — should differ from close."""
        pitches = realize_voicing("Cmaj7", "drop2", "mid_high", voice_count=4, extensions=[])
        assert len(pitches) == 4
        close_pitches = realize_voicing("Cmaj7", "close", "mid_high", voice_count=4, extensions=[])
        assert pitches != close_pitches  # must produce different voicing


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


class TestCheckVoiceLeading:
    def test_identical_voicings(self):
        result = check_voice_leading(["C4", "E4", "G4", "B4"], ["C4", "E4", "G4", "B4"])
        assert isinstance(result, VoiceLeadingCheck)
        assert result.common_tones == 4
        assert result.total_semitone_distance == 0
        assert result.max_leap == 0

    def test_smooth_voice_leading(self):
        # Cmaj7 → Am7: C stays, E stays, G stays, B→A (2 semitones)
        result = check_voice_leading(["C4", "E4", "G4", "B4"], ["C4", "E4", "G4", "A4"])
        assert result.common_tones == 3
        assert result.total_semitone_distance == 2
        assert result.max_leap == 2

    def test_parallel_fifths_detected(self):
        # Voice 1: C4→D4, Voice 2: G4→A4 — parallel fifths
        result = check_voice_leading(["C4", "G4"], ["D4", "A4"])
        assert result.has_parallel_fifths is True

    def test_no_parallel_fifths(self):
        result = check_voice_leading(["C4", "E4", "G4"], ["C4", "F4", "A4"])
        assert result.has_parallel_fifths is False

    def test_parallel_octaves_detected(self):
        # Voice 1: C3→D3, Voice 2: C4→D4 — parallel octaves
        result = check_voice_leading(["C3", "C4"], ["D3", "D4"])
        assert result.has_parallel_octaves is True

    def test_unequal_voice_counts(self):
        """When voice counts differ, analyzes min(len) voices."""
        result = check_voice_leading(
            ["C4", "E4", "G4", "B4"],  # 4 voices
            ["C4", "E4", "G4"],         # 3 voices
        )
        assert result.common_tones == 3  # first 3 match
        assert result.total_semitone_distance == 0
