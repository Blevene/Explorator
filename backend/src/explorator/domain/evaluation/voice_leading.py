"""Voice leading evaluator — deterministic scoring of voicing transitions.

Analyzes voice leading quality between adjacent voicing events using
music21_adapter.check_voice_leading(). Fully deterministic, no LLM calls.
"""

from ulid import ULID

from explorator.adapters.music21_adapter import check_voice_leading
from explorator.models.evaluation import VoiceLeadingEvaluation
from explorator.models.realization import VoicingPlan
from explorator.utils import utc_now


class VoiceLeadingEvaluator:
    """Deterministic voice leading quality evaluator."""

    def evaluate(
        self,
        voicing_plan: VoicingPlan,
        candidate_id: str,
    ) -> VoiceLeadingEvaluation:
        """Score voice leading across all adjacent voicing transitions.

        Single chord (or no chords) returns a perfect score of 10.0 on all fields.
        """
        events = voicing_plan.voicing_events
        now = utc_now()
        eval_id = f"vl_eval_{ULID()}"

        if len(events) < 2:
            return VoiceLeadingEvaluation(
                id=eval_id,
                type="voice_leading_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="voice_leading",
                smoothness_score=10.0,
                common_tone_retention_score=10.0,
                awkward_leap_penalty=10.0,
                resolution_quality=10.0,
            )

        # Accumulate metrics across transitions
        total_common_tones = 0
        total_semitone_distance = 0
        max_leap_anywhere = 0
        parallel_violations = 0
        large_distance_transitions = 0
        smooth_transitions = 0

        n_transitions = len(events) - 1

        for i in range(n_transitions):
            prev = events[i]
            nxt = events[i + 1]
            result = check_voice_leading(prev.pitches, nxt.pitches)

            total_common_tones += result.common_tones
            total_semitone_distance += result.total_semitone_distance

            if result.max_leap > max_leap_anywhere:
                max_leap_anywhere = result.max_leap

            if result.has_parallel_fifths or result.has_parallel_octaves:
                parallel_violations += 1

            # Average semitone distance per voice for this transition
            n_voices = min(len(prev.pitches), len(nxt.pitches))
            avg_dist_this = (
                result.total_semitone_distance / n_voices if n_voices > 0 else 0
            )
            if avg_dist_this > 8:
                large_distance_transitions += 1

            if result.common_tones >= 2:
                smooth_transitions += 1

        avg_common_tones = total_common_tones / n_transitions
        avg_semitone_distance = total_semitone_distance / n_transitions

        # Overall score
        score = 10.0
        score -= parallel_violations * 1.5
        score -= large_distance_transitions * 0.5
        smooth_bonus = min(2.0, smooth_transitions * 0.5)
        score += smooth_bonus
        overall = max(0.0, min(10.0, score))

        # Individual field normalization
        smoothness = max(0.0, 10.0 - (avg_semitone_distance / 2.0))
        common_tone_retention = min(10.0, avg_common_tones * 3.3)
        leap_penalty = max(0.0, 10.0 - (max_leap_anywhere / 2.4))
        resolution = max(0.0, 10.0 - (parallel_violations * 1.5))

        return VoiceLeadingEvaluation(
            id=eval_id,
            type="voice_leading_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="voice_leading",
            smoothness_score=round(smoothness, 3),
            common_tone_retention_score=round(common_tone_retention, 3),
            awkward_leap_penalty=round(leap_penalty, 3),
            resolution_quality=round(resolution, 3),
        )

    def overall_score(self, evaluation: VoiceLeadingEvaluation) -> float:
        """Compute the overall 0-10 score as the average of the 4 field scores."""
        fields = [
            evaluation.smoothness_score,
            evaluation.common_tone_retention_score,
            evaluation.awkward_leap_penalty,
            evaluation.resolution_quality,
        ]
        return round(sum(fields) / len(fields), 3)
