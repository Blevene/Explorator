"""MIDI renderer — converts VoicingPlan + BassLine to MIDI bytes."""

from __future__ import annotations

import io

import pretty_midi

from explorator.models.melody import MelodicComplement
from explorator.models.realization import BassLine, VoicingPlan
from explorator.utils import pitch_str_to_midi


class MidiRenderError(Exception):
    """Raised when MIDI rendering fails validation."""


_CHORD_VELOCITY = 80
_CHORD_PROGRAM = 0   # Acoustic Grand Piano
_BASS_PROGRAM = 33   # Electric Bass Finger
_MELODY_PROGRAM = 73  # Flute (clean melodic lead)


def _time_sec(bar: int, beat: float, beats_per_bar: int, bpm: float) -> float:
    """Convert 0-indexed bar + 1-indexed beat to absolute seconds."""
    return (bar * beats_per_bar + (beat - 1)) * (60.0 / bpm)


def _duration_sec(duration_beats: float, bpm: float) -> float:
    return duration_beats * (60.0 / bpm)


def _build_tracks(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int,
    melodic_complement: MelodicComplement | None = None,
) -> tuple[pretty_midi.Instrument, pretty_midi.Instrument, pretty_midi.Instrument | None]:
    """Build chord, bass, and optional melody Instrument objects."""
    chord_inst = pretty_midi.Instrument(program=_CHORD_PROGRAM, name="Chords")
    for ev in voicing_plan.voicing_events:
        start = _time_sec(ev.bar, ev.beat, beats_per_bar, bpm)
        end = start + _duration_sec(ev.duration_beats, bpm)
        for pitch in ev.pitches:
            midi_num = pitch_str_to_midi(pitch)
            chord_inst.notes.append(
                pretty_midi.Note(velocity=_CHORD_VELOCITY, pitch=midi_num, start=start, end=end)
            )

    bass_inst = pretty_midi.Instrument(program=_BASS_PROGRAM, name="Bass")
    for ev in bass_line.note_events:
        start = _time_sec(ev.bar, ev.beat, beats_per_bar, bpm)
        end = start + _duration_sec(ev.duration_beats, bpm)
        midi_num = pitch_str_to_midi(ev.pitch)
        bass_inst.notes.append(
            pretty_midi.Note(velocity=ev.velocity, pitch=midi_num, start=start, end=end)
        )

    melody_inst: pretty_midi.Instrument | None = None
    if melodic_complement and melodic_complement.note_events:
        melody_inst = pretty_midi.Instrument(program=_MELODY_PROGRAM, name="Melody")
        for ev in melodic_complement.note_events:
            start = _time_sec(ev.bar, ev.beat, beats_per_bar, bpm)
            end = start + _duration_sec(ev.duration_beats, bpm)
            midi_num = pitch_str_to_midi(ev.pitch)
            melody_inst.notes.append(
                pretty_midi.Note(velocity=ev.velocity, pitch=midi_num, start=start, end=end)
            )

    total_notes = len(chord_inst.notes) + len(bass_inst.notes) + (len(melody_inst.notes) if melody_inst else 0)
    if total_notes == 0:
        raise MidiRenderError("No notes to render — VoicingPlan, BassLine, and MelodicComplement are all empty")

    return chord_inst, bass_inst, melody_inst


def _to_bytes(midi: pretty_midi.PrettyMIDI) -> bytes:
    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()


def render_combined_midi(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int = 4,
    melodic_complement: MelodicComplement | None = None,
) -> bytes:
    """One MIDI file with tracks (chords + bass + optional melody)."""
    chord_inst, bass_inst, melody_inst = _build_tracks(
        voicing_plan, bass_line, bpm, beats_per_bar, melodic_complement,
    )
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    midi.instruments.append(chord_inst)
    midi.instruments.append(bass_inst)
    if melody_inst:
        midi.instruments.append(melody_inst)
    return _to_bytes(midi)


def render_separate_midi(
    voicing_plan: VoicingPlan,
    bass_line: BassLine,
    bpm: float,
    beats_per_bar: int = 4,
    melodic_complement: MelodicComplement | None = None,
) -> dict[str, bytes]:
    """Separate MIDI files: {"chords": bytes, "bass": bytes, "melody": bytes (if present)}."""
    chord_inst, bass_inst, melody_inst = _build_tracks(
        voicing_plan, bass_line, bpm, beats_per_bar, melodic_complement,
    )

    chords_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    chords_midi.instruments.append(chord_inst)

    bass_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    bass_midi.instruments.append(bass_inst)

    result: dict[str, bytes] = {"chords": _to_bytes(chords_midi), "bass": _to_bytes(bass_midi)}

    if melody_inst:
        melody_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        melody_midi.instruments.append(melody_inst)
        result["melody"] = _to_bytes(melody_midi)

    return result
