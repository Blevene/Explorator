"""Tests for melody models."""

from explorator.models.melody import (
    MelodicComplement,
    MelodicNoteEvent,
    MelodicPreferences,
    MelodicStrategyResponse,
    PhraseInstruction,
)


class TestMelodicNoteEvent:
    def test_defaults(self) -> None:
        e = MelodicNoteEvent(bar=1, pitch="C5")
        assert e.beat == 1.0
        assert e.duration_beats == 1.0
        assert e.velocity == 80

    def test_explicit(self) -> None:
        e = MelodicNoteEvent(bar=2, beat=2.5, duration_beats=0.5, pitch="E5", velocity=100)
        assert e.bar == 2
        assert e.beat == 2.5
        assert e.pitch == "E5"


class TestMelodicComplement:
    def test_defaults(self) -> None:
        mc = MelodicComplement(
            id="mc_test",
            type="melodic_complement",
            status="completed",
            arrangement_candidate_id="arr_test",
        )
        assert mc.groove_pattern_id is None
        assert mc.note_events == []
        assert mc.range_low == ""
        assert mc.range_high == ""
        assert mc.contour_type == ""
        assert mc.source_strategy == ""

    def test_with_events(self) -> None:
        events = [MelodicNoteEvent(bar=1, pitch="C5"), MelodicNoteEvent(bar=1, beat=2.0, pitch="D5")]
        mc = MelodicComplement(
            id="mc_test",
            type="melodic_complement",
            status="completed",
            arrangement_candidate_id="arr_test",
            note_events=events,
            range_low="C5",
            range_high="C6",
            contour_type="arch",
        )
        assert len(mc.note_events) == 2
        assert mc.range_low == "C5"


class TestPhraseInstruction:
    def test_creation(self) -> None:
        pi = PhraseInstruction(
            start_bar=1,
            end_bar=4,
            contour="arch",
            density="moderate",
            strong_beat_targets=["root", "5th"],
            rest_after=True,
        )
        assert pi.start_bar == 1
        assert pi.end_bar == 4
        assert pi.rest_after is True


class TestMelodicStrategyResponse:
    def test_creation(self) -> None:
        sr = MelodicStrategyResponse(
            range_low="C5",
            range_high="C6",
            overall_contour="arch",
            phrase_instructions=[
                PhraseInstruction(
                    start_bar=1, end_bar=4, contour="arch",
                    density="moderate", strong_beat_targets=["root"], rest_after=False,
                ),
            ],
        )
        assert sr.range_low == "C5"
        assert len(sr.phrase_instructions) == 1
        assert sr.rationale == ""

    def test_rationale_max_length(self) -> None:
        import pytest
        with pytest.raises(Exception):
            MelodicStrategyResponse(
                range_low="C5",
                range_high="C6",
                overall_contour="arch",
                phrase_instructions=[],
                rationale="x" * 201,
            )


class TestMelodicPreferences:
    def test_defaults(self) -> None:
        mp = MelodicPreferences()
        assert mp.motion_preference == "stepwise"
        assert mp.density == "moderate"
        assert mp.phrase_length == 4

    def test_from_genre_tendencies(self) -> None:
        tendencies = {
            "motion_preference": "leaping",
            "density": "sparse",
            "phrase_length": "2",
            "strong_beat_preference": "roots_and_fifths",
        }
        mp = MelodicPreferences.from_genre_tendencies(tendencies)
        assert mp.motion_preference == "leaping"
        assert mp.density == "sparse"
        assert mp.phrase_length == 2

    def test_from_empty_tendencies(self) -> None:
        mp = MelodicPreferences.from_genre_tendencies({})
        assert mp.motion_preference == "stepwise"
