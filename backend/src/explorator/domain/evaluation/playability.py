"""Playability evaluator — deterministic scoring of physical playability.

Analyzes span and voice count per voicing event to assess whether the
arrangement is physically comfortable to play on a keyboard instrument.
Guitar playability is deferred to a later milestone.
"""

from ulid import ULID

from explorator.models.evaluation import PlayabilityEvaluation
from explorator.models.realization import VoicingPlan
from explorator.utils import utc_now


class PlayabilityEvaluator:
    """Deterministic playability evaluator for keyboard voicings."""

    def evaluate(
        self,
        voicing_plan: VoicingPlan,
        candidate_id: str,
    ) -> PlayabilityEvaluation:
        """Score playability across all voicing events.

        Penalties:
        - Span > 15 semitones:  -3.0
        - Span 13-15 semitones: -1.0
        - Voice count > 5:      -2.0

        piano_playability = 10 - avg_penalty, clamped [0, 10].
        guitar_playability = 0.0 (deferred).
        ensemble_playability = piano_playability.
        """
        now = utc_now()
        eval_id = f"play_eval_{ULID()}"

        events = voicing_plan.voicing_events
        recommendations: list[str] = []

        if not events:
            return PlayabilityEvaluation(
                id=eval_id,
                type="playability_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="playability",
                piano_playability=10.0,
                guitar_playability=0.0,
                ensemble_playability=10.0,
                simplification_recommendations=[],
            )

        total_penalty = 0.0
        wide_span_bars: list[int] = []
        excess_voice_bars: list[int] = []

        for event in events:
            midi_values = _pitches_to_midi(event.pitches)
            penalty = 0.0

            if midi_values:
                span = max(midi_values) - min(midi_values)
                voice_count = len(midi_values)

                if span > 15:
                    penalty += 3.0
                    wide_span_bars.append(event.bar)
                elif span >= 13:
                    penalty += 1.0
                    wide_span_bars.append(event.bar)

                if voice_count > 5:
                    penalty += 2.0
                    excess_voice_bars.append(event.bar)

            total_penalty += penalty

        avg_penalty = total_penalty / len(events)
        piano_score = max(0.0, min(10.0, 10.0 - avg_penalty))

        # Build recommendations
        if wide_span_bars:
            unique_bars = sorted(set(wide_span_bars))
            bar_str = ", ".join(str(b) for b in unique_bars)
            recommendations.append(
                f"Wide stretch detected in bar(s) {bar_str} — consider inversion or register shift"
            )
        if excess_voice_bars:
            unique_bars = sorted(set(excess_voice_bars))
            bar_str = ", ".join(str(b) for b in unique_bars)
            recommendations.append(
                f"Too many voices (>5) in bar(s) {bar_str} — consider reducing voice count"
            )

        return PlayabilityEvaluation(
            id=eval_id,
            type="playability_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="playability",
            piano_playability=round(piano_score, 3),
            guitar_playability=0.0,
            ensemble_playability=round(piano_score, 3),
            simplification_recommendations=recommendations,
        )

    def overall_score(self, evaluation: PlayabilityEvaluation) -> float:
        """Return piano_playability as the primary overall score."""
        return evaluation.piano_playability


def _pitches_to_midi(pitches: list[str]) -> list[int]:
    """Convert named pitch strings to MIDI values, silently skipping failures."""
    from music21 import pitch as m21pitch

    result = []
    for p in pitches:
        try:
            result.append(m21pitch.Pitch(p).midi)
        except Exception:
            pass
    return result
