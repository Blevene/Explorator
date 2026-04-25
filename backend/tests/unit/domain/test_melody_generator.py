"""Tests for MelodyGenerator domain service."""


from explorator.domain.realization.melody import MelodyGenerator
from explorator.models.melody import (
    MelodicComplement,
    MelodicNoteEvent,
    MelodicStrategyResponse,
    PhraseInstruction,
)
from explorator.models.realization import VoicingEvent
from explorator.utils import pitch_str_to_midi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strategy(
    range_low="C5",
    range_high="C6",
    phrases=None,
):
    if phrases is None:
        phrases = [
            PhraseInstruction(
                start_bar=0,
                end_bar=3,
                contour="arch",
                density="moderate",
                strong_beat_targets=["root", "5th"],
                rest_after=False,
            )
        ]
    return MelodicStrategyResponse(
        range_low=range_low,
        range_high=range_high,
        overall_contour="arch",
        phrase_instructions=phrases,
    )


def _voicing_event(bar, pitches, chord_symbol="C"):
    return VoicingEvent(
        bar=bar,
        pitches=pitches,
        chord_symbol=chord_symbol,
        duration_beats=4.0,
    )


_CHORDS_4 = ["Cmaj7", "Am7", "Fmaj7", "G7"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMelodyGeneratorBasic:
    def test_produces_melodic_complement(self):
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) > 0
        # Every event must be a MelodicNoteEvent
        for ev in result.note_events:
            assert isinstance(ev, MelodicNoteEvent)

    def test_all_pitches_within_range(self):
        gen = MelodyGenerator()
        strat = _strategy(range_low="C5", range_high="C6")
        result = gen.realize(
            strategy=strat,
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)],
            beat_grid=None,
            motion_preference="stepwise",
        )
        lo = pitch_str_to_midi("C5")
        hi = pitch_str_to_midi("C6")
        for ev in result.note_events:
            midi = pitch_str_to_midi(ev.pitch)
            assert lo <= midi <= hi, (
                f"Pitch {ev.pitch} (MIDI {midi}) outside range C5-C6 ({lo}-{hi})"
            )

    def test_no_voicing_collisions(self):
        """No melody note should be unison or minor-2nd with any voicing pitch on same bar."""
        gen = MelodyGenerator()
        voicings = [
            _voicing_event(0, ["C4", "E4", "G4", "B4"]),
            _voicing_event(1, ["A3", "C4", "E4", "G4"]),
            _voicing_event(2, ["F4", "A4", "C5", "E5"]),
            _voicing_event(3, ["G3", "B3", "D4", "F4"]),
        ]
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=voicings,
            beat_grid=None,
            motion_preference="stepwise",
        )
        for ev in result.note_events:
            mel_midi = pitch_str_to_midi(ev.pitch)
            for v in voicings:
                if v.bar == ev.bar:
                    for vp in v.pitches:
                        v_midi = pitch_str_to_midi(vp)
                        diff = abs(mel_midi - v_midi)
                        assert diff not in (0, 1), (
                            f"Collision: melody {ev.pitch} vs voicing {vp} on bar {ev.bar} "
                            f"(diff={diff} semitones)"
                        )

    def test_final_note_is_chord_tone(self):
        """Last note of the melody must be a chord tone of the final chord."""
        from music21 import harmony

        from explorator.adapters.music21_adapter import _normalize_chord_symbol

        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert len(result.note_events) > 0
        last = result.note_events[-1]
        # Get chord tones from final chord
        final_sym = _normalize_chord_symbol(_CHORDS_4[-1])
        chord = harmony.ChordSymbol(final_sym)
        chord_pitch_names = {p.name for p in chord.pitches}
        # Extract note name from pitch (strip octave)
        import re

        m = re.match(r"^([A-G][#b\-]?)", last.pitch)
        assert m, f"Cannot parse pitch: {last.pitch}"
        note_name = m.group(1).replace("b", "-")
        assert note_name in chord_pitch_names, (
            f"Final note {last.pitch} (name={note_name}) not in chord tones "
            f"{chord_pitch_names} of {_CHORDS_4[-1]}"
        )

    def test_empty_chords_returns_empty(self):
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=[],
            key_center="C",
            mode="major",
            voicing_events=[],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) == 0

    def test_sparse_density_beats_1_and_3(self):
        """Sparse density should only produce notes on beats 1.0 and 3.0."""
        gen = MelodyGenerator()
        strat = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=3,
                    contour="static",
                    density="sparse",
                    strong_beat_targets=["root"],
                    rest_after=False,
                )
            ]
        )
        result = gen.realize(
            strategy=strat,
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)],
            beat_grid=None,
            motion_preference="stepwise",
        )
        for ev in result.note_events:
            assert ev.beat in (1.0, 3.0), (
                f"Sparse density should only have beats 1.0 and 3.0, got {ev.beat}"
            )


class TestMelodyGeneratorContour:
    def test_rest_after_skips_last_beat(self):
        """rest_after=True should produce fewer notes than rest_after=False."""
        gen = MelodyGenerator()
        strat_no_rest = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=3,
                    contour="static",
                    density="moderate",
                    strong_beat_targets=["root"],
                    rest_after=False,
                )
            ]
        )
        strat_rest = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=3,
                    contour="static",
                    density="moderate",
                    strong_beat_targets=["root"],
                    rest_after=True,
                )
            ]
        )
        voicings = [_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)]
        r_no = gen.realize(
            strategy=strat_no_rest,
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=voicings,
            beat_grid=None,
            motion_preference="stepwise",
        )
        r_rest = gen.realize(
            strategy=strat_rest,
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=voicings,
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert len(r_rest.note_events) < len(r_no.note_events)

    def test_active_density_has_eighth_notes(self):
        """Active density should include beats on .5 positions."""
        gen = MelodyGenerator()
        strat = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=1,
                    contour="static",
                    density="active",
                    strong_beat_targets=["root"],
                    rest_after=False,
                )
            ]
        )
        result = gen.realize(
            strategy=strat,
            chord_symbols=["C", "C"],
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C3", "E3", "G3"]) for i in range(2)],
            beat_grid=None,
            motion_preference="stepwise",
        )
        beats = {ev.beat for ev in result.note_events}
        half_beats = {b for b in beats if b != int(b)}
        assert len(half_beats) > 0, "Active density should include .5 beat positions"


class TestMelodyGeneratorGroove:
    def test_groove_driven_beat_grid(self):
        """When beat_grid is provided, melody uses those positions."""
        gen = MelodyGenerator()
        # Groove events with absolute beats: bar 0 = 1.0-4.x, bar 1 = 5.0-8.x
        beat_grid = [
            {"beat": 1.0, "duration_beats": 1.0, "velocity": 80, "accent": True},
            {"beat": 2.5, "duration_beats": 0.5, "velocity": 60, "accent": False},
            {"beat": 5.0, "duration_beats": 1.0, "velocity": 80, "accent": True},
            {"beat": 7.0, "duration_beats": 1.0, "velocity": 70, "accent": False},
        ]
        strat = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=1,
                    contour="static",
                    density="active",  # active so all grid positions pass filtering
                    strong_beat_targets=["root"],
                    rest_after=False,
                )
            ]
        )
        result = gen.realize(
            strategy=strat,
            chord_symbols=["C", "Am"],
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C3", "E3", "G3"]) for i in range(2)],
            beat_grid=beat_grid,
            motion_preference="stepwise",
        )
        # Should have events corresponding to the groove positions
        assert len(result.note_events) > 0
        # Check per-bar beats match what groove provides
        bar0_beats = {ev.beat for ev in result.note_events if ev.bar == 0}
        bar1_beats = {ev.beat for ev in result.note_events if ev.bar == 1}
        # bar 0: absolute 1.0 → per-bar 1.0, absolute 2.5 → per-bar 2.5
        assert 1.0 in bar0_beats
        # bar 1: absolute 5.0 → per-bar 1.0, absolute 7.0 → per-bar 3.0
        assert 1.0 in bar1_beats


class TestMelodyGeneratorEdgeCases:
    def test_single_chord_single_bar(self):
        gen = MelodyGenerator()
        strat = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=0,
                    contour="static",
                    density="moderate",
                    strong_beat_targets=["root"],
                    rest_after=False,
                )
            ]
        )
        result = gen.realize(
            strategy=strat,
            chord_symbols=["C"],
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(0, ["C3", "E3", "G3"])],
            beat_grid=None,
            motion_preference="stepwise",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) > 0

    def test_leaping_motion_allows_larger_intervals(self):
        """Leaping motion should not crash and should produce valid output."""
        gen = MelodyGenerator()
        result = gen.realize(
            strategy=_strategy(),
            chord_symbols=_CHORDS_4,
            key_center="C",
            mode="major",
            voicing_events=[_voicing_event(i, ["C4", "E4", "G4"]) for i in range(4)],
            beat_grid=None,
            motion_preference="leaping",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) > 0

    def test_minor_mode(self):
        """Minor mode should produce valid output."""
        gen = MelodyGenerator()
        strat = _strategy(
            phrases=[
                PhraseInstruction(
                    start_bar=0,
                    end_bar=3,
                    contour="descending",
                    density="moderate",
                    strong_beat_targets=["root", "3rd"],
                    rest_after=False,
                )
            ]
        )
        result = gen.realize(
            strategy=strat,
            chord_symbols=["Cm", "Fm", "Gm", "Cm"],
            key_center="C",
            mode="minor",
            voicing_events=[
                _voicing_event(i, ["C4", "E-4", "G4"]) for i in range(4)
            ],
            beat_grid=None,
            motion_preference="mixed",
        )
        assert isinstance(result, MelodicComplement)
        assert len(result.note_events) > 0
