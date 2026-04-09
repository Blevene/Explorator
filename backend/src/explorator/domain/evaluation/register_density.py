"""Register density evaluator — deterministic scoring of register and density balance.

Analyzes mud zone crowding, spacing balance, register alignment, and
bass-voicing separation per bar. Fully deterministic, no LLM calls.
"""

from ulid import ULID

from explorator.adapters.music21_adapter import _REGISTER_BOUNDS
from explorator.models.evaluation import RegisterDensityEvaluation
from explorator.models.realization import BassLine, VoicingPlan
from explorator.utils import utc_now

_MUD_ZONE_LOW = 36
_MUD_ZONE_HIGH = 52


class RegisterDensityEvaluator:
    """Deterministic register and density balance evaluator."""

    def evaluate(
        self,
        voicing_plan: VoicingPlan,
        bass_line: BassLine,
        candidate_id: str,
        preferred_register: str = "mid_high",
    ) -> RegisterDensityEvaluation:
        """Score register/density quality across all bars."""
        now = utc_now()
        eval_id = f"rd_eval_{ULID()}"

        # Group voicing events and bass notes by bar
        voicing_by_bar: dict[int, list[list[str]]] = {}
        for event in voicing_plan.voicing_events:
            voicing_by_bar.setdefault(event.bar, []).append(event.pitches)

        bass_by_bar: dict[int, list[str]] = {}
        for note in bass_line.note_events:
            bass_by_bar.setdefault(note.bar, []).append(note.pitch)

        all_bars = sorted(set(voicing_by_bar) | set(bass_by_bar))

        if not all_bars:
            # No events — perfect score
            return RegisterDensityEvaluation(
                id=eval_id,
                type="register_density_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="register_density",
                register_balance_score=10.0,
                mud_risk_score=10.0,
                overcrowding_risk_score=10.0,
                spacing_quality=10.0,
            )

        register_bounds = _REGISTER_BOUNDS.get(preferred_register, _REGISTER_BOUNDS["mid_high"])
        reg_low, reg_high = register_bounds[0], register_bounds[1]

        mud_bars = 0
        imbalance_bars = 0
        register_miss_bars = 0
        collision_bars = 0

        for bar in all_bars:
            voicing_events = voicing_by_bar.get(bar, [])
            bass_pitches = bass_by_bar.get(bar, [])

            # Convert all voicing pitches in this bar to MIDI
            all_voicing_midi: list[int] = []
            for pitches in voicing_events:
                for p in pitches:
                    midi = _pitch_to_midi(p)
                    if midi is not None:
                        all_voicing_midi.append(midi)

            bass_midi_list: list[int] = []
            for p in bass_pitches:
                midi = _pitch_to_midi(p)
                if midi is not None:
                    bass_midi_list.append(midi)

            # 1. Mud zone check: count pitches in [36, 52]
            mud_count = sum(
                1 for m in all_voicing_midi + bass_midi_list
                if _MUD_ZONE_LOW <= m <= _MUD_ZONE_HIGH
            )
            if mud_count > 2:
                mud_bars += 1

            # 2. Spacing balance: flag only when BOTH a wide gap (>19) AND a tight gap (<3)
            #    exist in the same bar — that's genuine imbalance, not intentional open voicing
            if all_voicing_midi:
                sorted_midi = sorted(all_voicing_midi)
                if len(sorted_midi) >= 3:
                    gaps = [sorted_midi[i + 1] - sorted_midi[i] for i in range(len(sorted_midi) - 1)]
                    has_wide = any(g > 19 for g in gaps)
                    has_tight = any(g < 3 for g in gaps)
                    if has_wide and has_tight:
                        imbalance_bars += 1

            # 3. Register alignment: voicing centroid vs preferred register
            if all_voicing_midi:
                centroid = round(sum(all_voicing_midi) / len(all_voicing_midi))
                if centroid < reg_low or centroid > reg_high:
                    register_miss_bars += 1

            # 4. Bass-voicing separation: lowest voicing MIDI - bass MIDI
            if all_voicing_midi and bass_midi_list:
                lowest_voicing = min(all_voicing_midi)
                bass_midi = min(bass_midi_list)
                if lowest_voicing - bass_midi < 7:
                    collision_bars += 1

        # Field normalization
        register_balance = max(0.0, 10.0 - (register_miss_bars * 2.5))
        mud_risk = max(0.0, 10.0 - (mud_bars * 2.0))
        overcrowding_risk = max(0.0, 10.0 - (imbalance_bars * 1.5))
        spacing_quality = max(0.0, 10.0 - (collision_bars * 2.5))

        return RegisterDensityEvaluation(
            id=eval_id,
            type="register_density_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="register_density",
            register_balance_score=round(register_balance, 3),
            mud_risk_score=round(mud_risk, 3),
            overcrowding_risk_score=round(overcrowding_risk, 3),
            spacing_quality=round(spacing_quality, 3),
        )

    def overall_score(self, evaluation: RegisterDensityEvaluation) -> float:
        """Compute the overall 0-10 score as the average of the 4 field scores."""
        fields = [
            evaluation.register_balance_score,
            evaluation.mud_risk_score,
            evaluation.overcrowding_risk_score,
            evaluation.spacing_quality,
        ]
        return round(sum(fields) / len(fields), 3)


def _pitch_to_midi(pitch: str) -> int | None:
    """Convert a named pitch string (e.g. 'C4', 'B-3') to MIDI number."""
    try:
        from music21 import pitch as m21pitch
        return m21pitch.Pitch(pitch).midi
    except Exception:
        return None
