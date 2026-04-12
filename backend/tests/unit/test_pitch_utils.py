"""Tests for pitch_str_to_midi utility."""

import pytest

from explorator.utils import pitch_str_to_midi


class TestPitchStrToMidi:
    """Pure-Python pitch string to MIDI note number conversion."""

    def test_middle_c(self):
        assert pitch_str_to_midi("C4") == 60

    def test_a3(self):
        assert pitch_str_to_midi("A3") == 57

    def test_c3(self):
        assert pitch_str_to_midi("C3") == 48

    def test_sharp(self):
        assert pitch_str_to_midi("F#4") == 66

    def test_flat_standard(self):
        assert pitch_str_to_midi("Bb3") == 58

    def test_flat_music21_format(self):
        """music21 uses B- not Bb."""
        assert pitch_str_to_midi("B-3") == 58

    def test_e_flat_music21(self):
        assert pitch_str_to_midi("E-4") == 63

    def test_lowest_midi(self):
        assert pitch_str_to_midi("C-1") == 0

    def test_high_note(self):
        assert pitch_str_to_midi("C8") == 108

    def test_invalid_pitch_raises(self):
        with pytest.raises(ValueError):
            pitch_str_to_midi("X9")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            pitch_str_to_midi("")
