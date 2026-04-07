"""Tests for RegisterDensityEvaluator."""

from explorator.domain.evaluation.register_density import RegisterDensityEvaluator
from explorator.models.realization import BassLine, BassNoteEvent, VoicingEvent, VoicingPlan


def _make_voicing_plan(events: list[VoicingEvent]) -> VoicingPlan:
    return VoicingPlan(
        id="vp_test",
        type="voicing_plan",
        status="completed",
        voicing_events=events,
    )


def _make_bass_line(notes: list[BassNoteEvent]) -> BassLine:
    return BassLine(
        id="bl_test",
        type="bass_line",
        status="completed",
        note_events=notes,
    )


def _voicing(bar: int, pitches: list[str]) -> VoicingEvent:
    return VoicingEvent(bar=bar, pitches=pitches, chord_symbol="C")


def _bass(bar: int, pitch: str) -> BassNoteEvent:
    return BassNoteEvent(bar=bar, pitch=pitch)


class TestRegisterDensityEvaluatorCleanArrangement:
    """A well-spaced arrangement in the correct register scores high."""

    def test_clean_mid_high_arrangement_scores_high(self) -> None:
        # Voicing in mid_high (C4-C6), good spacing, no mud, no collision
        plan = _make_voicing_plan([
            _voicing(1, ["E4", "B4", "G5"]),
            _voicing(2, ["F4", "A4", "C5"]),
        ])
        bass = _make_bass_line([
            _bass(1, "C2"),
            _bass(2, "F2"),
        ])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_1", preferred_register="mid_high")
        assert result.register_balance_score >= 7.0
        assert result.mud_risk_score == 10.0
        assert result.spacing_quality == 10.0

    def test_empty_plan_returns_perfect_scores(self) -> None:
        plan = _make_voicing_plan([])
        bass = _make_bass_line([])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_0", preferred_register="mid_high")
        assert result.register_balance_score == 10.0
        assert result.mud_risk_score == 10.0
        assert result.overcrowding_risk_score == 10.0
        assert result.spacing_quality == 10.0


class TestRegisterDensityEvaluatorMudZone:
    """More than 2 pitches in MIDI 36-52 (C2-E3) triggers mud penalty."""

    def test_three_notes_in_mud_zone_penalizes(self) -> None:
        # C2=36, D2=38, E2=40 — all in mud zone, plus bass also in mud zone
        plan = _make_voicing_plan([
            _voicing(1, ["C2", "D2", "E2"]),
        ])
        bass = _make_bass_line([_bass(1, "G2")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_mud", preferred_register="mid_high")
        # mud_bars=1 → mud_risk = max(0, 10 - 1*2.0) = 8.0
        assert result.mud_risk_score == 8.0

    def test_two_notes_in_mud_zone_no_penalty(self) -> None:
        # Only 2 pitches in mud zone — no violation
        plan = _make_voicing_plan([
            _voicing(1, ["C2", "E2", "G4", "B4"]),
        ])
        bass = _make_bass_line([_bass(1, "C3")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_mud2", preferred_register="mid_high")
        # C2=36 (mud), E2=40 (mud), G4=67 (not mud), B4=71 (not mud), C3=48 (mud)
        # total mud pitches = 3 (C2, E2, C3) > 2 → violation
        assert result.mud_risk_score == 8.0


class TestRegisterDensityEvaluatorBassCollision:
    """Bass-voicing collision is detected when lowest voicing - bass < 7 semitones."""

    def test_collision_detected_when_too_close(self) -> None:
        # Lowest voicing = E3 (52), bass = C3 (48): 52-48 = 4 < 7 → collision
        plan = _make_voicing_plan([
            _voicing(1, ["E3", "G3", "B3"]),
        ])
        bass = _make_bass_line([_bass(1, "C3")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_coll", preferred_register="mid_high")
        # collision_bars=1 → spacing_quality = max(0, 10 - 1*2.5) = 7.5
        assert result.spacing_quality == 7.5

    def test_no_collision_when_well_separated(self) -> None:
        # Lowest voicing = C4 (60), bass = C2 (36): 60-36 = 24 >= 7 → no collision
        plan = _make_voicing_plan([
            _voicing(1, ["C4", "E4", "G4"]),
        ])
        bass = _make_bass_line([_bass(1, "C2")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_sep", preferred_register="mid_high")
        assert result.spacing_quality == 10.0


class TestRegisterDensityEvaluatorRegisterMisalignment:
    """Voicing centroid outside preferred register reduces register_balance_score."""

    def test_low_register_voicing_misses_mid_high(self) -> None:
        # Voicing at C2-G2, centroid ≈ 40 — well outside mid_high [60-84]
        plan = _make_voicing_plan([
            _voicing(1, ["C2", "E2", "G2"]),
        ])
        bass = _make_bass_line([_bass(1, "C1")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_reg", preferred_register="mid_high")
        # register_miss_bars=1 → register_balance = max(0, 10 - 1*2.5) = 7.5
        assert result.register_balance_score == 7.5

    def test_aligned_voicing_scores_high_register_balance(self) -> None:
        # Voicing at C5-G5, centroid ≈ 72 — inside mid_high [60-84]
        plan = _make_voicing_plan([
            _voicing(1, ["C5", "E5", "G5"]),
        ])
        bass = _make_bass_line([_bass(1, "C2")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_reg2", preferred_register="mid_high")
        assert result.register_balance_score == 10.0


class TestRegisterDensityEvaluatorEntityFields:
    """Entity metadata is correctly populated."""

    def test_entity_fields(self) -> None:
        plan = _make_voicing_plan([_voicing(1, ["C4", "E4", "G4"])])
        bass = _make_bass_line([_bass(1, "C2")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_meta")
        assert result.id.startswith("rd_eval_")
        assert result.type == "register_density_evaluation"
        assert result.status == "completed"
        assert result.evaluation_type == "register_density"
        assert result.candidate_id == "cand_meta"


class TestRegisterDensityEvaluatorOverallScore:
    """overall_score returns average of 4 field scores."""

    def test_overall_score_is_average(self) -> None:
        plan = _make_voicing_plan([_voicing(1, ["C4", "E4", "G4"])])
        bass = _make_bass_line([_bass(1, "C2")])
        ev = RegisterDensityEvaluator()
        result = ev.evaluate(plan, bass, "cand_ov")
        expected = (
            result.register_balance_score
            + result.mud_risk_score
            + result.overcrowding_risk_score
            + result.spacing_quality
        ) / 4
        assert abs(ev.overall_score(result) - expected) < 0.001
