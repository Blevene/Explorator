"""Groove evaluator — deterministic scoring of groove quality.

Three scoring dimensions: groove_authenticity, rhythmic_coherence, style_alignment.
Fully deterministic, no LLM calls.
"""

from ulid import ULID

from explorator.models.evaluation import GrooveEvaluation
from explorator.models.groove import GroovePattern, GroovePreferences
from explorator.utils import utc_now

# Expected density ranges by comp_density
_DENSITY_RANGES: dict[str, tuple[float, float]] = {
    "sparse": (0.0, 0.4),
    "low": (0.1, 0.45),
    "medium": (0.35, 0.75),
    "dense": (0.65, 1.0),
    "sparse_to_dense": (0.15, 0.65),
}

# Expected templates by syncopation_level
_SYNCOPATION_TEMPLATES: dict[str, set[str]] = {
    "minimal": {"sparse"},
    "light": {"straight_eighths", "sparse", "dotted"},
    "low": {"straight_eighths", "sparse", "dotted"},
    "moderate": {"dotted", "syncopated", "straight_eighths"},
    "heavy": {"syncopated"},
}


class GrooveEvaluator:
    """Deterministic groove quality evaluator."""

    def evaluate(
        self,
        pattern: GroovePattern,
        prefs: GroovePreferences,
        candidate_id: str,
    ) -> GrooveEvaluation:
        """Score groove quality across three dimensions."""
        now = utc_now()
        eval_id = f"gev_{ULID()}"

        # Empty events → all scores = 2.0
        if not pattern.pattern_events:
            return GrooveEvaluation(
                id=eval_id,
                type="groove_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="groove_evaluation",
                groove_authenticity=2.0,
                rhythmic_coherence=2.0,
                style_alignment=2.0,
            )

        groove_authenticity = self._score_groove_authenticity(pattern, prefs)
        rhythmic_coherence = self._score_rhythmic_coherence(pattern, prefs)
        style_alignment = self._score_style_alignment(pattern, prefs)

        return GrooveEvaluation(
            id=eval_id,
            type="groove_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="groove_evaluation",
            groove_authenticity=round(groove_authenticity, 3),
            rhythmic_coherence=round(rhythmic_coherence, 3),
            style_alignment=round(style_alignment, 3),
        )

    def _score_groove_authenticity(
        self, pattern: GroovePattern, prefs: GroovePreferences
    ) -> float:
        """Composite: density match + template match + swing consistency."""
        score = 10.0

        # Density match vs genre expectations (up to -4.0)
        density_range = _DENSITY_RANGES.get(prefs.comp_density, (0.35, 0.75))
        lo, hi = density_range
        midpoint = (lo + hi) / 2.0
        half_width = (hi - lo) / 2.0
        if half_width > 0:
            distance = max(0.0, abs(pattern.density - midpoint) - half_width)
            # Normalize: max possible distance is ~1.0, penalty up to 4.0
            penalty = min(4.0, (distance / max(half_width, 0.1)) * 4.0)
        else:
            penalty = 4.0 if pattern.density != midpoint else 0.0
        score -= penalty

        # Template match vs syncopation level (-2.0 if mismatch)
        expected_templates = _SYNCOPATION_TEMPLATES.get(prefs.syncopation_level, set())
        if expected_templates and pattern.source_template not in expected_templates:
            score -= 2.0

        # Swing consistency: if swing_amount is set but template is straight, penalize (-1.0)
        if pattern.swing_amount > 0.1 and pattern.source_template == "straight_eighths":
            score -= 1.0

        return max(0.0, min(10.0, score))

    def _score_rhythmic_coherence(
        self, pattern: GroovePattern, prefs: GroovePreferences
    ) -> float:
        """Accent regularity and velocity consistency."""
        score = 10.0
        events = pattern.pattern_events

        # Off-beat accent penalty in non-syncopated patterns (-0.5 each)
        is_syncopated = prefs.syncopation_level in {"moderate", "heavy"}
        if not is_syncopated:
            for ev in events:
                if ev.accent:
                    # Beat positions that are off-beat: not on integer beats
                    beat_frac = ev.beat % 1.0
                    if beat_frac != 0.0:
                        score -= 0.5

        # Velocity consistency
        velocities = [ev.velocity for ev in events]
        vel_range = max(velocities) - min(velocities)
        if vel_range < 10:
            score -= 1.0  # too flat
        elif vel_range > 60:
            score -= 1.5  # too wild

        return max(0.0, min(10.0, score))

    def _score_style_alignment(
        self, pattern: GroovePattern, prefs: GroovePreferences
    ) -> float:
        """Parameter match vs genre expectations."""
        score = 10.0

        # Density distance from expected midpoint (up to -3.0)
        density_range = _DENSITY_RANGES.get(prefs.comp_density, (0.35, 0.75))
        lo, hi = density_range
        midpoint = (lo + hi) / 2.0
        half_width = (hi - lo) / 2.0
        if half_width > 0:
            distance = max(0.0, abs(pattern.density - midpoint) - half_width)
            penalty = min(3.0, (distance / max(half_width, 0.1)) * 3.0)
        else:
            penalty = 3.0 if pattern.density != midpoint else 0.0
        score -= penalty

        # Template mismatch (-3.0)
        expected_templates = _SYNCOPATION_TEMPLATES.get(prefs.syncopation_level, set())
        if expected_templates and pattern.source_template not in expected_templates:
            score -= 3.0

        return max(0.0, min(10.0, score))

    def overall_score(self, evaluation: GrooveEvaluation) -> float:
        """Average of 3 dimensions, rounded to 2 decimal places."""
        total = (
            evaluation.groove_authenticity
            + evaluation.rhythmic_coherence
            + evaluation.style_alignment
        )
        return round(total / 3, 2)
