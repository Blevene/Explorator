"""Tests for PlayabilityEvaluator."""

from explorator.domain.evaluation.playability import PlayabilityEvaluator
from explorator.models.realization import VoicingEvent, VoicingPlan


def _make_plan(events: list[VoicingEvent]) -> VoicingPlan:
    return VoicingPlan(
        id="vp_test",
        type="voicing_plan",
        status="completed",
        voicing_events=events,
    )


def _event(bar: int, pitches: list[str]) -> VoicingEvent:
    return VoicingEvent(bar=bar, pitches=pitches, chord_symbol="C")


class TestPlayabilityEvaluatorComfortableVoicing:
    """Comfortable voicings (span ≤ 12, voice_count ≤ 5) score high."""

    def test_close_voicing_scores_10(self) -> None:
        # Span: B4(71) - C4(60) = 11 semitones, 4 voices
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "B4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_1")
        assert result.piano_playability == 10.0
        assert result.ensemble_playability == 10.0

    def test_empty_plan_returns_perfect_score(self) -> None:
        plan = _make_plan([])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_0")
        assert result.piano_playability == 10.0
        assert result.ensemble_playability == 10.0
        assert result.simplification_recommendations == []

    def test_multiple_comfortable_chords_score_10(self) -> None:
        plan = _make_plan([
            _event(1, ["C4", "E4", "G4"]),
            _event(2, ["F4", "A4", "C5"]),
            _event(3, ["G4", "B4", "D5"]),
        ])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_multi")
        assert result.piano_playability == 10.0


class TestPlayabilityEvaluatorWideStretch:
    """Spans > 15 semitones incur a -3.0 penalty; spans 13-15 incur -1.0."""

    def test_span_over_15_reduces_score_by_3(self) -> None:
        # C4(60) to A5(81): span = 21 semitones
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "A5"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_wide")
        assert result.piano_playability == 7.0

    def test_span_13_reduces_score_by_1(self) -> None:
        # C4(60) to A4(69): span = 9 — comfortable
        # C4(60) to A-4(68): span = 8 — comfortable
        # C4(60) to C#5(73): span = 13 semitones → -1.0
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "C#5"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_13")
        assert result.piano_playability == 9.0

    def test_span_15_reduces_score_by_1(self) -> None:
        # C4(60) to D#5(75): span = 15 semitones → -1.0
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "D#5"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_15")
        assert result.piano_playability == 9.0

    def test_wide_stretch_generates_recommendation(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "A5"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_rec")
        assert len(result.simplification_recommendations) >= 1
        assert "stretch" in result.simplification_recommendations[0].lower()

    def test_mixed_bars_averages_penalties(self) -> None:
        # Bar 1: span = 21 → penalty -3.0
        # Bar 2: span = 9  → penalty 0.0
        # avg = -1.5, score = 8.5
        plan = _make_plan([
            _event(1, ["C4", "E4", "G4", "A5"]),
            _event(2, ["C4", "E4", "G4"]),
        ])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_mix")
        assert result.piano_playability == 8.5


class TestPlayabilityEvaluatorTooManyVoices:
    """More than 5 voices incurs a -2.0 penalty."""

    def test_six_voices_reduces_score_by_2(self) -> None:
        plan = _make_plan([_event(1, ["C4", "D4", "E4", "G4", "A4", "B4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_6v")
        assert result.piano_playability == 8.0

    def test_too_many_voices_generates_recommendation(self) -> None:
        plan = _make_plan([_event(1, ["C4", "D4", "E4", "G4", "A4", "B4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_6v_rec")
        assert len(result.simplification_recommendations) >= 1
        assert "voice" in result.simplification_recommendations[0].lower() or \
               any("voice" in r.lower() for r in result.simplification_recommendations)

    def test_five_voices_no_penalty(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4", "B4", "D5"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_5v")
        # Span D5(62)-C4(60) wait: D5=74, C4=60 → span=14 → -1.0
        # But we care about voice count: 5 voices is fine
        # Span: D5(74) - C4(60) = 14 → -1.0
        assert result.piano_playability == 9.0


class TestPlayabilityEvaluatorGuitarPlayability:
    """guitar_playability is always 0.0 (deferred)."""

    def test_guitar_playability_is_zero(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_guitar")
        assert result.guitar_playability == 0.0

    def test_guitar_playability_zero_even_for_wide_voicing(self) -> None:
        plan = _make_plan([_event(1, ["C2", "E4", "G6"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_guitar2")
        assert result.guitar_playability == 0.0


class TestPlayabilityEvaluatorEntityFields:
    """Entity metadata is correctly populated."""

    def test_entity_fields(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_meta")
        assert result.id.startswith("play_eval_")
        assert result.type == "playability_evaluation"
        assert result.status == "completed"
        assert result.evaluation_type == "playability"
        assert result.candidate_id == "cand_meta"


class TestPlayabilityEvaluatorOverallScore:
    """overall_score returns piano_playability."""

    def test_overall_score_matches_piano_playability(self) -> None:
        plan = _make_plan([_event(1, ["C4", "E4", "G4"])])
        ev = PlayabilityEvaluator()
        result = ev.evaluate(plan, "cand_ov")
        assert ev.overall_score(result) == result.piano_playability
