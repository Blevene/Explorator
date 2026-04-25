"""Tests for VoicingGenerator inversion sweep voice-leading optimization."""

from explorator.domain.realization.voicing import VoicingGenerator
from explorator.models.realization import (
    ChordVoicingInstruction,
    VariantConfig,
    VoicingPreferences,
    VoicingStrategyResponse,
)


def _make_strategy(chords: list[str]) -> VoicingStrategyResponse:
    return VoicingStrategyResponse(
        global_strategy="test",
        density_level="medium",
        voice_count=4,
        per_chord=[
            ChordVoicingInstruction(
                chord_symbol=c,
                voicing_type="close",
                target_register="mid",
                extensions_to_include=[],
            )
            for c in chords
        ],
    )


class TestVoicingInversionSweep:
    def test_produces_valid_voicings(self):
        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        # Use 7th chords to guarantee 4 voices
        chords = ["Cmaj7", "Fmaj7", "G7", "Cmaj7"]
        plan = gen.realize(
            _make_strategy(chords), chords, prefs, VariantConfig(voicing_type="close")
        )
        assert len(plan.voicing_events) == 4
        for event in plan.voicing_events:
            assert len(event.pitches) == 4

    def test_reduces_voice_movement(self):
        from explorator.adapters.music21_adapter import check_voice_leading

        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        # Use 7th chords for stable 4-voice results
        chords = ["Cmaj7", "Am7", "Fmaj7", "G7"]
        plan = gen.realize(
            _make_strategy(chords), chords, prefs, VariantConfig(voicing_type="close")
        )
        total_distance = 0
        for i in range(len(plan.voicing_events) - 1):
            vl = check_voice_leading(
                plan.voicing_events[i].pitches, plan.voicing_events[i + 1].pitches
            )
            total_distance += vl.total_semitone_distance
        assert total_distance < 60

    def test_avoids_parallel_fifths(self):
        from explorator.adapters.music21_adapter import check_voice_leading

        gen = VoicingGenerator()
        prefs = VoicingPreferences(default_register="mid")
        # I-IV-ii-V progression: inversions help avoid parallel fifths here
        chords = ["Cmaj7", "Fmaj7", "Dm7", "G7"]
        plan = gen.realize(
            _make_strategy(chords), chords, prefs, VariantConfig(voicing_type="close")
        )
        parallel_count = 0
        for i in range(len(plan.voicing_events) - 1):
            vl = check_voice_leading(
                plan.voicing_events[i].pitches, plan.voicing_events[i + 1].pitches
            )
            if vl.has_parallel_fifths:
                parallel_count += 1
        assert parallel_count <= 1
