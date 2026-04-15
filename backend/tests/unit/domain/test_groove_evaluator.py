"""Tests for GrooveEvaluator."""

from explorator.domain.evaluation.groove import GrooveEvaluator
from explorator.models.groove import GrooveEvent, GroovePattern, GroovePreferences


def _make_pattern(
    density: float,
    source_template: str,
    events: list[GrooveEvent],
    swing_amount: float = 0.0,
) -> GroovePattern:
    return GroovePattern(
        id="gp_test",
        type="groove_pattern",
        status="completed",
        session_id="sess_test",
        genre="test_genre",
        density=density,
        source_template=source_template,
        swing_amount=swing_amount,
        pattern_events=events,
    )


def _make_prefs(
    comp_density: str = "medium",
    syncopation_level: str = "light",
    articulation_style: str = "straight",
) -> GroovePreferences:
    return GroovePreferences(
        comp_density=comp_density,
        syncopation_level=syncopation_level,
        articulation_style=articulation_style,
    )


def _event(beat: float, velocity: int, accent: bool = False) -> GrooveEvent:
    return GrooveEvent(beat=beat, duration_beats=0.5, velocity=velocity, accent=accent)


class TestGrooveEvaluatorEntityFields:
    """Entity metadata is correctly populated."""

    def test_entity_fields(self) -> None:
        pattern = _make_pattern(0.5, "straight_eighths", [_event(1.0, 80)])
        prefs = _make_prefs()
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_meta")
        assert result.id.startswith("gev_")
        assert result.type == "groove_evaluation"
        assert result.status == "completed"
        assert result.evaluation_type == "groove_evaluation"
        assert result.candidate_id == "cand_meta"


class TestGrooveEvaluatorEmptyEvents:
    """Empty pattern events → all scores = 2.0."""

    def test_empty_events_scores_low(self) -> None:
        pattern = _make_pattern(0.5, "straight_eighths", [])
        prefs = _make_prefs()
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_empty")
        assert result.groove_authenticity <= 3.0
        assert result.rhythmic_coherence <= 3.0
        assert result.style_alignment <= 3.0

    def test_empty_events_scores_equal_2(self) -> None:
        pattern = _make_pattern(0.5, "straight_eighths", [])
        prefs = _make_prefs()
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_empty2")
        assert result.groove_authenticity == 2.0
        assert result.rhythmic_coherence == 2.0
        assert result.style_alignment == 2.0


class TestGrooveEvaluatorPerfectAlignment:
    """Perfect alignment: medium density + straight_eighths + light syncopation → high scores."""

    def test_perfect_alignment_scores_high(self) -> None:
        # medium density (0.5 in range 0.35-0.75), straight_eighths matches light syncopation
        events = [_event(float(i), 80) for i in range(1, 9)]
        pattern = _make_pattern(0.5, "straight_eighths", events)
        prefs = _make_prefs(comp_density="medium", syncopation_level="light")
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_perfect")
        assert result.groove_authenticity >= 7.0
        assert result.rhythmic_coherence >= 7.0
        assert result.style_alignment >= 7.0


class TestGrooveEvaluatorMismatch:
    """Mismatch: sparse prefs + syncopated dense pattern → style_alignment < 6.0."""

    def test_mismatch_style_alignment_low(self) -> None:
        # dense pattern (density=0.9, out of sparse range 0.0-0.4)
        # syncopated template doesn't match sparse comp_density expectations
        events = [_event(float(i) * 0.5, 90) for i in range(1, 16)]
        pattern = _make_pattern(0.9, "syncopated", events)
        prefs = _make_prefs(comp_density="sparse", syncopation_level="minimal")
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_mismatch")
        assert result.style_alignment < 6.0


class TestGrooveEvaluatorOverallScore:
    """overall_score returns average of 3 dimensions, rounded to 2 decimal places."""

    def test_overall_score_is_average(self) -> None:
        events = [_event(float(i), 80) for i in range(1, 9)]
        pattern = _make_pattern(0.5, "straight_eighths", events)
        prefs = _make_prefs()
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_overall")
        expected = round(
            (result.groove_authenticity + result.rhythmic_coherence + result.style_alignment) / 3,
            2,
        )
        assert ev.overall_score(result) == expected

    def test_overall_score_rounded_to_2dp(self) -> None:
        events = [_event(float(i), 80) for i in range(1, 5)]
        pattern = _make_pattern(0.5, "straight_eighths", events)
        prefs = _make_prefs()
        ev = GrooveEvaluator()
        result = ev.evaluate(pattern, prefs, "cand_round")
        score = ev.overall_score(result)
        # Should have at most 2 decimal places
        assert score == round(score, 2)
