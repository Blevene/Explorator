"""Tests for MIDI renderer."""

import pretty_midi
import pytest

from explorator.domain.export.midi_renderer import (
    MidiRenderError,
    render_combined_midi,
    render_separate_midi,
)
from explorator.models.realization import BassLine, BassNoteEvent, VoicingEvent, VoicingPlan


def _make_voicing_plan() -> VoicingPlan:
    return VoicingPlan(
        id="vp-1",
        type="VoicingPlan",
        status="active",
        voicing_events=[
            VoicingEvent(
                bar=0, beat=1.0, duration_beats=4.0, pitches=["C3", "E3", "G3"], chord_symbol="C"
            ),
            VoicingEvent(
                bar=1, beat=1.0, duration_beats=4.0, pitches=["F3", "A3", "C4"], chord_symbol="F"
            ),
        ],
    )


def _make_bass_line() -> BassLine:
    return BassLine(
        id="bl-1",
        type="BassLine",
        status="active",
        note_events=[
            BassNoteEvent(bar=0, beat=1.0, duration_beats=2.0, pitch="C2", velocity=90),
            BassNoteEvent(bar=0, beat=3.0, duration_beats=2.0, pitch="E2", velocity=80),
            BassNoteEvent(bar=1, beat=1.0, duration_beats=4.0, pitch="F2", velocity=85),
        ],
    )


class TestRenderCombinedMidi:
    def test_returns_bytes(self):
        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        assert isinstance(result, bytes)

    def test_parseable_by_pretty_midi(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        assert len(midi.instruments) == 2

    def test_chord_track_has_correct_notes(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        chord_track = midi.instruments[0]
        # 2 chords * 3 pitches each = 6 notes
        assert len(chord_track.notes) == 6

    def test_bass_track_has_correct_notes(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        bass_track = midi.instruments[1]
        assert len(bass_track.notes) == 3

    def test_chord_velocity_is_80(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        for note in midi.instruments[0].notes:
            assert note.velocity == 80

    def test_bass_velocity_from_event(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        bass_notes = sorted(midi.instruments[1].notes, key=lambda n: n.start)
        assert bass_notes[0].velocity == 90
        assert bass_notes[1].velocity == 80

    def test_time_conversion_at_120bpm(self):
        """Bar 0, beat 1 at 120 BPM = 0.0 seconds. Bar 1, beat 1 = 2.0 seconds."""
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        chord_notes = sorted(midi.instruments[0].notes, key=lambda n: n.start)
        assert abs(chord_notes[0].start - 0.0) < 0.01
        assert abs(chord_notes[3].start - 2.0) < 0.01  # bar 1 starts at 2.0s

    def test_gm_programs(self):
        import io

        result = render_combined_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        midi = pretty_midi.PrettyMIDI(io.BytesIO(result))
        assert midi.instruments[0].program == 0  # Acoustic Grand Piano
        assert midi.instruments[1].program == 33  # Electric Bass Finger


class TestRenderSeparateMidi:
    def test_returns_dict_with_chords_and_bass(self):
        result = render_separate_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        assert isinstance(result, dict)
        assert "chords" in result
        assert "bass" in result

    def test_each_file_has_one_instrument(self):
        import io

        result = render_separate_midi(_make_voicing_plan(), _make_bass_line(), bpm=120.0)
        chords_midi = pretty_midi.PrettyMIDI(io.BytesIO(result["chords"]))
        bass_midi = pretty_midi.PrettyMIDI(io.BytesIO(result["bass"]))
        assert len(chords_midi.instruments) == 1
        assert len(bass_midi.instruments) == 1


class TestMidiValidation:
    def test_empty_voicing_raises(self):
        empty_vp = VoicingPlan(id="vp-e", type="VoicingPlan", status="active", voicing_events=[])
        empty_bl = BassLine(id="bl-e", type="BassLine", status="active", note_events=[])
        with pytest.raises(MidiRenderError):
            render_combined_midi(empty_vp, empty_bl, bpm=120.0)
