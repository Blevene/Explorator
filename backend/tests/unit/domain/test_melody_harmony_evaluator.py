"""Tests for MelodyHarmonyEvaluator."""

from explorator.domain.evaluation.melody_harmony import MelodyHarmonyEvaluator
from explorator.models.melody import MelodicComplement, MelodicNoteEvent
from explorator.models.realization import VoicingEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_complement(events: list[MelodicNoteEvent]) -> MelodicComplement:
    return MelodicComplement(
        id="mel_test",
        type="melodic_complement",
        status="completed",
        arrangement_candidate_id="arr_test",
        note_events=events,
    )


def _make_voicing_event(
    bar: int, pitches: list[str], chord_symbol: str, beat: float = 1.0
) -> VoicingEvent:
    return VoicingEvent(bar=bar, beat=beat, pitches=pitches, chord_symbol=chord_symbol)


def _note(bar: int, beat: float, pitch: str) -> MelodicNoteEvent:
    return MelodicNoteEvent(bar=bar, beat=beat, pitch=pitch)


# ---------------------------------------------------------------------------
# Entity fields
# ---------------------------------------------------------------------------


class TestMelodyHarmonyEvaluatorEntityFields:
    """Entity metadata is correctly populated."""

    def test_entity_fields(self) -> None:
        notes = [_note(1, 1.0, "C5"), _note(1, 2.0, "E5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "G3", "E4"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_meta")
        assert result.id.startswith("mhev_")
        assert result.type == "melody_harmony_evaluation"
        assert result.status == "completed"
        assert result.evaluation_type == "melody_harmony_evaluation"
        assert result.candidate_id == "cand_meta"


# ---------------------------------------------------------------------------
# Melody support score
# ---------------------------------------------------------------------------


class TestMelodySupportScore:
    """melody_support_score reflects chord-tone ratio and voice-leading smoothness."""

    def test_all_chord_tones_scores_high(self) -> None:
        # C5, E5, G5 on beats 1.0 are all C major chord tones → high chord-tone ratio
        notes = [
            _note(1, 1.0, "C5"),
            _note(1, 2.0, "E5"),
            _note(1, 3.0, "G5"),
        ]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_chord_tones")
        # All strong-beat notes (1.0 and 3.0) are C-major chord tones → ratio = 1.0
        # Voice-leading: C5→E5 = 4 semitones (at threshold for stepwise), E5→G5 = 3 semitones (≤4)
        assert result.melody_support_score >= 7.0

    def test_non_chord_tones_reduce_score(self) -> None:
        # D5 and F#5 are not in Cmaj7 → lower chord-tone ratio
        notes = [
            _note(1, 1.0, "D5"),
            _note(1, 2.0, "F#5"),
            _note(1, 3.0, "D5"),
        ]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3", "B3"], "Cmaj7")]
        ev = MelodyHarmonyEvaluator()
        result_non = ev.evaluate(complement, ["Cmaj7"], voicings, "stepwise", "cand_non_chord")

        # Compare with all chord tones
        notes_ct = [
            _note(1, 1.0, "C5"),
            _note(1, 2.0, "E5"),
            _note(1, 3.0, "G5"),
        ]
        complement_ct = _make_complement(notes_ct)
        result_ct = ev.evaluate(
            complement_ct, ["Cmaj7"], voicings, "stepwise", "cand_chord_tones_cmaj7"
        )
        assert result_non.melody_support_score < result_ct.melody_support_score

    def test_stepwise_motion_scores_high_smoothness(self) -> None:
        # C5→D5→E5→F5 — all steps ≤ 4 semitones → smoothness ratio = 1.0
        notes = [
            _note(1, 1.0, "C5"),
            _note(1, 2.0, "D5"),
            _note(1, 3.0, "E5"),
            _note(1, 4.0, "F5"),
        ]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_stepwise")
        # All intervals ≤ 4 semitones → smoothness = 10.0
        # melody_support_score is average of chord_tone_ratio_score and smoothness_score
        assert result.melody_support_score >= 5.0

    def test_leaping_motion_with_leaping_preference_scores_high(self) -> None:
        # Large leaps with leaping preference → high smoothness score
        # C5→G5 = 7 semitones — at threshold for leaping (≤7)
        notes = [
            _note(1, 1.0, "C5"),
            _note(1, 2.0, "G5"),
            _note(1, 3.0, "C5"),
            _note(1, 4.0, "G5"),
        ]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result_leaping = ev.evaluate(complement, ["C"], voicings, "leaping", "cand_leaping")
        result_stepwise = ev.evaluate(
            complement, ["C"], voicings, "stepwise", "cand_stepwise_big_leaps"
        )
        # With leaping preference, 7-semitone interval is within threshold → higher score
        assert result_leaping.melody_support_score >= result_stepwise.melody_support_score

    def test_single_note_smoothness_no_intervals(self) -> None:
        # Single note: no consecutive intervals → smoothness defaults gracefully
        notes = [_note(1, 1.0, "C5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_single")
        # Should not crash, score in valid range
        assert 0.0 <= result.melody_support_score <= 10.0


# ---------------------------------------------------------------------------
# Collision risk score
# ---------------------------------------------------------------------------


class TestCollisionRiskScore:
    """collision_risk_score penalizes unisons and minor 2nds with voicing notes."""

    def test_no_collisions_scores_10(self) -> None:
        # Melody in C6 range, voicing in C3 range — no collisions
        notes = [_note(1, 1.0, "C6"), _note(1, 2.0, "E6"), _note(1, 3.0, "G6")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_no_collision")
        assert result.collision_risk_score == 10.0

    def test_unison_collision_penalizes(self) -> None:
        # Melody C4 == voicing C4 → collision
        notes = [_note(1, 1.0, "C4"), _note(1, 2.0, "E5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_unison")
        assert result.collision_risk_score < 10.0

    def test_minor_second_collision_penalizes(self) -> None:
        # Melody C#4 vs voicing C4 → 1 semitone apart → collision
        notes = [_note(1, 1.0, "C#4"), _note(1, 2.0, "E5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_minor2nd")
        assert result.collision_risk_score < 10.0

    def test_major_second_no_collision(self) -> None:
        # Melody D4 vs voicing C4 → 2 semitones → NOT a collision
        notes = [_note(1, 1.0, "D4"), _note(1, 2.0, "E5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_major2nd")
        assert result.collision_risk_score == 10.0

    def test_collision_across_bars_only_same_bar(self) -> None:
        # Melody note in bar 2, voicing in bar 1 — no collision (different bars)
        notes = [_note(2, 1.0, "C4")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_diff_bar")
        assert result.collision_risk_score == 10.0

    def test_multiple_collisions_accumulate(self) -> None:
        # Two melody notes both collide with voicing on same bar
        notes = [_note(1, 1.0, "C4"), _note(1, 2.0, "E4")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E4", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_multi_collision")
        assert result.collision_risk_score < 10.0

    def test_collision_floor_at_zero(self) -> None:
        # Every melody note collides → floor at 0.0
        notes = [_note(1, beat, "C4") for beat in [1.0, 2.0, 3.0, 4.0]]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C4", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_all_collide")
        assert result.collision_risk_score >= 0.0

    def test_empty_melody_returns_default(self) -> None:
        complement = _make_complement([])
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_empty")
        assert result.melody_support_score == 5.0
        assert result.collision_risk_score == 5.0


# ---------------------------------------------------------------------------
# Overall score
# ---------------------------------------------------------------------------


class TestOverallScore:
    """overall_score is average of melody_support_score and collision_risk_score."""

    def test_overall_is_average(self) -> None:
        notes = [_note(1, 1.0, "C5"), _note(1, 3.0, "E5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "stepwise", "cand_overall")
        expected = round((result.melody_support_score + result.collision_risk_score) / 2, 2)
        assert ev.overall_score(result) == expected

    def test_overall_rounded_to_2dp(self) -> None:
        notes = [_note(1, 1.0, "D5"), _note(1, 3.0, "F#5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "mixed", "cand_round")
        score = ev.overall_score(result)
        assert score == round(score, 2)

    def test_overall_in_valid_range(self) -> None:
        notes = [_note(1, 1.0, "C5"), _note(1, 2.0, "G5")]
        complement = _make_complement(notes)
        voicings = [_make_voicing_event(1, ["C3", "E3", "G3"], "C")]
        ev = MelodyHarmonyEvaluator()
        result = ev.evaluate(complement, ["C"], voicings, "leaping", "cand_range")
        score = ev.overall_score(result)
        assert 0.0 <= score <= 10.0
