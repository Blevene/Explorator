"""MelodyHarmonyEvaluator — deterministic scoring of melody-harmony compatibility.

Two scoring dimensions: melody_support_score, collision_risk_score.
Fully deterministic, no LLM calls.
"""

import music21

from ulid import ULID

from explorator.models.evaluation import MelodyHarmonyEvaluation
from explorator.models.melody import MelodicComplement
from explorator.models.realization import VoicingEvent
from explorator.utils import pitch_str_to_midi, utc_now

# Strong beats: downbeats 1 and 3 in a 4/4 bar
_STRONG_BEATS: frozenset[float] = frozenset({1.0, 3.0})

# Voice-leading smoothness threshold in semitones, by motion_preference
_SMOOTHNESS_THRESHOLDS: dict[str, int] = {
    "stepwise": 4,
    "leaping": 7,
    "mixed": 5,
}


def _chord_tones(chord_symbol: str) -> set[str]:
    """Return the set of pitch-class names for a chord symbol using music21.

    Returns an empty set if the chord cannot be parsed.
    """
    try:
        chord = music21.harmony.ChordSymbol(chord_symbol)
        return {p.name for p in chord.pitches}
    except Exception:  # noqa: BLE001
        return set()


class MelodyHarmonyEvaluator:
    """Deterministic melody-harmony compatibility evaluator."""

    def evaluate(
        self,
        complement: MelodicComplement,
        chord_symbols: list[str],
        voicing_events: list[VoicingEvent],
        motion_preference: str,
        candidate_id: str,
    ) -> MelodyHarmonyEvaluation:
        """Score melody-harmony compatibility across two dimensions."""
        now = utc_now()
        eval_id = f"mhev_{ULID()}"

        # Empty melody → both scores default to 5.0
        if not complement.note_events:
            return MelodyHarmonyEvaluation(
                id=eval_id,
                type="melody_harmony_evaluation",
                status="completed",
                created_at=now,
                updated_at=now,
                candidate_id=candidate_id,
                evaluation_type="melody_harmony_evaluation",
                melody_support_score=5.0,
                collision_risk_score=5.0,
            )

        melody_support = self._score_melody_support(complement, chord_symbols, voicing_events, motion_preference)
        collision_risk = self._score_collision_risk(complement, voicing_events)

        return MelodyHarmonyEvaluation(
            id=eval_id,
            type="melody_harmony_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate_id,
            evaluation_type="melody_harmony_evaluation",
            melody_support_score=round(melody_support, 3),
            collision_risk_score=round(collision_risk, 3),
        )

    # ------------------------------------------------------------------
    # Internal scoring helpers
    # ------------------------------------------------------------------

    def _score_melody_support(
        self,
        complement: MelodicComplement,
        chord_symbols: list[str],
        voicing_events: list[VoicingEvent],
        motion_preference: str,
    ) -> float:
        """Average of chord-tone ratio score and voice-leading smoothness score."""
        chord_tone_score = self._chord_tone_ratio_score(complement, chord_symbols, voicing_events)
        smoothness_score = self._voice_leading_smoothness_score(complement, motion_preference)
        return (chord_tone_score + smoothness_score) / 2.0

    def _chord_tone_ratio_score(
        self,
        complement: MelodicComplement,
        chord_symbols: list[str],
        voicing_events: list[VoicingEvent],
    ) -> float:
        """Proportion of strong-beat melody notes that are chord tones × 10.

        Strong beats are beat 1.0 and 3.0. The chord in effect for a given bar
        is taken from the voicing_events for that bar, falling back to
        chord_symbols by index.
        """
        # Build a bar → chord_symbol mapping from voicing events (prefer latest by beat)
        bar_chord: dict[int, str] = {}
        for ve in voicing_events:
            bar_chord[ve.bar] = ve.chord_symbol

        strong_beat_events = [
            ev for ev in complement.note_events if ev.beat in _STRONG_BEATS
        ]

        if not strong_beat_events:
            # No strong-beat notes: return neutral score
            return 5.0

        chord_tone_hits = 0
        for ev in strong_beat_events:
            # Determine chord symbol for this bar
            symbol = bar_chord.get(ev.bar)
            if symbol is None and chord_symbols:
                # Fall back to chord_symbols list by bar index (0-based)
                idx = max(0, ev.bar - 1)
                symbol = chord_symbols[min(idx, len(chord_symbols) - 1)]
            if symbol is None:
                continue

            tones = _chord_tones(symbol)
            if not tones:
                continue

            # Extract pitch class from the note pitch string (e.g., "C5" → "C")
            pitch_class = _pitch_class(ev.pitch)
            if pitch_class and pitch_class in tones:
                chord_tone_hits += 1

        ratio = chord_tone_hits / len(strong_beat_events)
        return ratio * 10.0

    def _voice_leading_smoothness_score(
        self,
        complement: MelodicComplement,
        motion_preference: str,
    ) -> float:
        """Proportion of consecutive intervals within threshold × 10.

        With only one note, there are no intervals — return 10.0 (perfect smoothness).
        """
        events = complement.note_events
        if len(events) < 2:
            return 10.0

        threshold = _SMOOTHNESS_THRESHOLDS.get(motion_preference, 5)

        smooth_count = 0
        total = len(events) - 1
        for i in range(total):
            try:
                midi_a = pitch_str_to_midi(events[i].pitch)
                midi_b = pitch_str_to_midi(events[i + 1].pitch)
            except ValueError:
                # Unparseable pitch — skip this interval
                total -= 1
                continue
            interval = abs(midi_b - midi_a)
            if interval <= threshold:
                smooth_count += 1

        if total == 0:
            return 10.0

        return (smooth_count / total) * 10.0

    def _score_collision_risk(
        self,
        complement: MelodicComplement,
        voicing_events: list[VoicingEvent],
    ) -> float:
        """Score based on absence of unisons and minor 2nds between melody and voicing.

        A collision is defined as a melody note whose MIDI value is within 1 semitone
        (inclusive) of any voicing note on the same bar.

        Formula: (1 - collision_count / total_melody_events) × 10, floored at 0.
        """
        total = len(complement.note_events)
        if total == 0:
            return 5.0

        # Build bar → list[int] (voicing MIDI notes)
        bar_voicing_midis: dict[int, list[int]] = {}
        for ve in voicing_events:
            midis: list[int] = []
            for p in ve.pitches:
                try:
                    midis.append(pitch_str_to_midi(p))
                except ValueError:
                    pass
            if midis:
                bar_voicing_midis.setdefault(ve.bar, []).extend(midis)

        collision_count = 0
        for ev in complement.note_events:
            voicing_midis = bar_voicing_midis.get(ev.bar)
            if not voicing_midis:
                continue
            try:
                melody_midi = pitch_str_to_midi(ev.pitch)
            except ValueError:
                continue
            for vm in voicing_midis:
                if abs(melody_midi - vm) <= 1:
                    collision_count += 1
                    break  # one collision per melody note is enough

        score = (1.0 - collision_count / total) * 10.0
        return max(0.0, score)

    def overall_score(self, evaluation: MelodyHarmonyEvaluation) -> float:
        """Average of melody_support_score and collision_risk_score, rounded to 2dp."""
        total = evaluation.melody_support_score + evaluation.collision_risk_score
        return round(total / 2, 2)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _pitch_class(pitch: str) -> str | None:
    """Extract the pitch class name from a pitch string like 'C#5' → 'C#', 'Bb4' → 'B-'.

    Returns the music21-compatible name (e.g., 'B-' for Bb).
    Returns None if unparseable.
    """
    s = pitch.strip()
    if not s:
        return None
    # Normalize: convert 'b' after a note letter to '-' for music21 compatibility
    # E.g., "Bb4" → pitch class "B-", "F#4" → pitch class "F#"
    import re
    m = re.match(r"^([A-Ga-g])([#b]?)(-?\d+)$", s)
    if m:
        note, acc, _ = m.groups()
        note = note.upper()
        if acc == "b":
            return f"{note}-"
        elif acc == "#":
            return f"{note}#"
        return note
    return None
