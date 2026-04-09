"""Tests for VoiceLeadingEvaluator."""

from explorator.domain.evaluation.voice_leading import VoiceLeadingEvaluator
from explorator.models.realization import VoicingEvent, VoicingPlan


def _make_plan(events: list[VoicingEvent]) -> VoicingPlan:
    return VoicingPlan(
        id="vp_test",
        type="voicing_plan",
        status="completed",
        voicing_events=events,
    )


def _event(bar: int, pitches: list[str], symbol: str = "C") -> VoicingEvent:
    return VoicingEvent(bar=bar, pitches=pitches, chord_symbol=symbol)


class TestVoiceLeadingEvaluatorSingleChord:
    """Single chord produces perfect scores."""

    def test_single_chord_returns_perfect_score(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "B4"])])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_1")
        assert result.smoothness_score == 10.0
        assert result.common_tone_retention_score == 10.0
        assert result.awkward_leap_penalty == 10.0
        assert result.resolution_quality == 10.0

    def test_single_chord_overall_score_is_10(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4"])])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_1")
        assert ev.overall_score(result) == 10.0

    def test_empty_plan_returns_perfect_score(self) -> None:
        plan = _make_plan([])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_1")
        assert result.smoothness_score == 10.0


class TestVoiceLeadingEvaluatorPerfectLeading:
    """Identical adjacent chords (all common tones, zero movement) score well."""

    def test_identical_chords_high_smoothness(self) -> None:
        pitches = ["C4", "E4", "G4", "B4"]
        plan = _make_plan([
            _event(1, pitches, "Cmaj7"),
            _event(2, pitches, "Cmaj7"),
            _event(3, pitches, "Cmaj7"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_2")
        # avg_semitone_distance == 0 → smoothness = 10
        assert result.smoothness_score == 10.0
        # all voices are common tones
        assert result.common_tone_retention_score == 10.0

    def test_identical_chords_no_parallel_violations(self) -> None:
        pitches = ["C4", "G4", "C5"]
        plan = _make_plan([
            _event(1, pitches, "C"),
            _event(2, pitches, "C"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_3")
        assert result.resolution_quality == 10.0


class TestVoiceLeadingEvaluatorParallelFifths:
    """Parallel fifths are penalized."""

    def test_parallel_fifths_reduce_resolution_quality(self) -> None:
        # C4-G4 → D4-A4: parallel fifths (both voices move up a whole step)
        plan = _make_plan([
            _event(1, ["C4", "G4"], "C5"),
            _event(2, ["D4", "A4"], "D5"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_4")
        # resolution_quality = 10.0 - 2.0 * 1 = 8.0
        assert result.resolution_quality < 10.0
        assert result.resolution_quality == 8.0

    def test_multiple_parallel_violations_stack(self) -> None:
        # Two transitions each with parallel fifths
        plan = _make_plan([
            _event(1, ["C4", "G4"], "C5"),
            _event(2, ["D4", "A4"], "D5"),
            _event(3, ["E4", "B4"], "E5"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_5")
        # resolution_quality = max(0, 10 - 2 * 2.0) = 6.0
        assert result.resolution_quality == 6.0


class TestVoiceLeadingEvaluatorLargeLeaps:
    """Large leaps across the whole arrangement reduce leap_penalty score."""

    def test_large_leap_reduces_awkward_leap_penalty(self) -> None:
        # C3=48, C5=72 — two adjacent voicings, lowest voice leaps 24 semitones
        # Sorted prev: [C3=48, E3=52, G3=55]; sorted next: [C5=72, E5=76, G5=79]
        # Each voice leaps 24 semitones; max_leap = 24
        plan = _make_plan([
            _event(1, ["C3", "E3", "G3"], "C"),
            _event(2, ["C5", "E5", "G5"], "C"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_6")
        # max_leap = 24, penalty = 10 - max(0, 24 - 7) * 0.5 = 10 - 8.5 = 1.5
        assert result.awkward_leap_penalty < 3.0

    def test_small_leaps_keep_penalty_high(self) -> None:
        # Stepwise motion (2 semitones per voice)
        plan = _make_plan([
            _event(1, ["C4", "E4", "G4"], "C"),
            _event(2, ["D4", "F4", "A4"], "Dm"),
        ])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_7")
        # max_leap = 2, awkward_leap_penalty = 10 - 2/2.4 ≈ 9.17
        assert result.awkward_leap_penalty > 8.0


class TestVoiceLeadingEvaluatorEntityFields:
    """Entity metadata is correctly populated."""

    def test_entity_fields(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4"])])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_99")
        assert result.id.startswith("vl_eval_")
        assert result.type == "voice_leading_evaluation"
        assert result.status == "completed"
        assert result.evaluation_type == "voice_leading"
        assert result.candidate_id == "cand_99"


class TestVoiceLeadingEvaluatorOverallScore:
    """overall_score returns average of 4 field scores."""

    def test_overall_score_is_average(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "B4"])])
        ev = VoiceLeadingEvaluator()
        result = ev.evaluate(plan, "cand_ov")
        expected = (
            result.smoothness_score
            + result.common_tone_retention_score
            + result.awkward_leap_penalty
            + result.resolution_quality
        ) / 4
        assert abs(ev.overall_score(result) - expected) < 0.001
