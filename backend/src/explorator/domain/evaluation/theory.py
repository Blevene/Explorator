"""Theory evaluation — deterministic checks + Gemini hybrid scoring.

Deterministic checks run first. Gemini Flash scores softer dimensions.
LLM is never the sole scoring authority.
"""

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.adapters.music21_adapter import analyze_roman_numerals, parse_chord_symbol
from explorator.models.evaluation import AggregateScorecard, TheoryEvaluation
from explorator.models.harmony import ProgressionCandidate
from explorator.utils import utc_now


def _root_interval(root_a: str, root_b: str) -> int | None:
    """Compute semitone interval from root_a up to root_b. Returns None on failure."""
    try:
        from music21 import pitch

        return (pitch.Pitch(root_b).midi - pitch.Pitch(root_a).midi) % 12
    except Exception:
        return None


def check_loopability(chord_symbols: list[str]) -> float:
    """Score how well a progression loops back to the start (0-10).

    Considers the relationship between the last chord and the first,
    plus whether the last chord has dominant function relative to the first.
    """
    if not chord_symbols or len(chord_symbols) < 2:
        return 5.0

    first = parse_chord_symbol(chord_symbols[0])
    last = parse_chord_symbol(chord_symbols[-1])

    if first.root == "unknown" or last.root == "unknown":
        return 5.0

    # Exact same chord — perfect loop
    if chord_symbols[0] == chord_symbols[-1]:
        return 9.5

    # Same root, different extension
    if first.root == last.root:
        return 9.0

    interval = _root_interval(last.root, first.root)
    if interval is None:
        return 5.5

    # V→I: dominant resolution (strongest loop point)
    # Also check if last chord is dominant quality (has "dominant" or "7" quality)
    is_dominant = last.quality in ("dominant", "dominant-ninth", "dominant-11th")

    if interval == 7:  # Perfect fifth up
        return 9.0 if is_dominant else 8.0

    if interval == 5:  # Perfect fourth up (IV→I plagal)
        return 7.5

    if interval == 2:  # Whole step up (bVII→I)
        return 7.0

    if interval == 3:  # Minor third (vi→I)
        return 7.0

    if interval == 10:  # Minor seventh up (ii→I, whole step down)
        return 6.5

    if interval == 1:  # Half step up (bII→I)
        return 6.5

    return 5.5


def check_cadence_quality(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score cadence quality based on the last two chords (0-10).

    Analyzes the penultimate → final chord motion relative to the key.
    """
    if len(chord_symbols) < 2:
        return 5.0

    last = parse_chord_symbol(chord_symbols[-1])
    penult = parse_chord_symbol(chord_symbols[-2])

    if last.root == "unknown" or penult.root == "unknown":
        return 5.0

    # Interval from key root to last chord root
    last_from_key = _root_interval(key, last.root)
    # Interval from penultimate to last
    penult_to_last = _root_interval(penult.root, last.root)

    if last_from_key is None or penult_to_last is None:
        return 5.0

    # Perfect authentic cadence: V→I (penult is 5th above last, last is tonic)
    if last_from_key == 0 and penult_to_last == 7:
        is_dominant = penult.quality in ("dominant", "dominant-ninth")
        return 9.5 if is_dominant else 8.5

    # Plagal cadence: IV→I
    if last_from_key == 0 and penult_to_last == 5:
        return 8.0

    # Half cadence: ends on V
    if last_from_key == 7:
        return 7.0

    # Deceptive cadence: V→vi
    if last_from_key == 9 and penult_to_last == 7:
        return 7.5

    # Ends on tonic but non-standard approach
    if last_from_key == 0:
        return 7.0

    # Ends on a non-tonic chord
    # Check if it at least has some harmonic motion
    if penult_to_last in (5, 7):  # Fourth or fifth motion
        return 6.5

    return 5.5


def check_theoretical_coherence(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score how well chords fit the key (0-10).

    Uses Roman numeral analysis to check diatonic fit.
    Chromatic/borrowed chords reduce score but aren't penalized heavily.
    """
    if not chord_symbols:
        return 5.0

    rna = analyze_roman_numerals(key, mode, chord_symbols)

    total = len(rna)
    if total == 0:
        return 5.0

    # Count: fully analyzed, low confidence, and failed
    analyzed = sum(1 for r in rna if r.confidence >= 0.8)
    partial = sum(1 for r in rna if 0.0 < r.confidence < 0.8)
    failed = sum(1 for r in rna if r.roman_numeral == "?")

    # Check for borrowed/chromatic chords (have b or # prefix)
    borrowed = sum(1 for r in rna if r.roman_numeral.startswith(("b", "#")))

    # Base score from analysis success rate
    base = 6.0 + (analyzed / total) * 3.0  # 6-9 range

    # Borrowed chords: slight penalty (they're intentional but less diatonic)
    base -= (borrowed / total) * 1.0

    # Failed analysis: stronger penalty
    base -= (failed / total) * 2.0

    # Bonus for variety: using more than 2 distinct chord qualities
    distinct_roots = len({parse_chord_symbol(s).root for s in chord_symbols if parse_chord_symbol(s).root != "unknown"})
    if distinct_roots >= 3:
        base += 0.5

    return max(3.0, min(10.0, round(base, 1)))


class GeminiScores(BaseModel):
    """Schema for Gemini's evaluation output."""

    genre_fit: float = Field(ge=0, le=10)
    emotional_fit: float = Field(ge=0, le=10)
    novelty: float = Field(ge=0, le=10)


class TheoryEvaluator:
    """Hybrid theory evaluator: deterministic + Gemini Flash."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def evaluate(
        self,
        candidate: ProgressionCandidate,
        genre: str,
        mood_targets: list[str],
    ) -> tuple[TheoryEvaluation, AggregateScorecard]:
        """Evaluate a progression candidate. Returns evaluation + scorecard."""
        chord_symbols = [e.symbol for e in candidate.chord_events]

        # Deterministic scores
        loopability = check_loopability(chord_symbols)
        cadence = check_cadence_quality(
            chord_symbols, candidate.key_center, candidate.mode
        )
        coherence = check_theoretical_coherence(
            chord_symbols, candidate.key_center, candidate.mode
        )

        # Gemini-assisted scores
        gemini_scores = await self._gemini_evaluate(
            chord_symbols, genre, mood_targets, candidate.key_center, candidate.mode
        )

        eval_id = f"eval_{ULID()}"
        now = utc_now()

        theory_eval = TheoryEvaluation(
            id=eval_id,
            type="theory_evaluation",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate.id,
            evaluation_type="theory",
            genre_fit=gemini_scores.genre_fit,
            emotional_fit=gemini_scores.emotional_fit,
            theoretical_coherence=coherence,
            cadence_quality=cadence,
            novelty=gemini_scores.novelty,
            loopability=loopability,
        )

        # Build aggregate scorecard
        scores = {
            "genre_fit": gemini_scores.genre_fit,
            "emotional_fit": gemini_scores.emotional_fit,
            "theoretical_coherence": coherence,
            "cadence_quality": cadence,
            "novelty": gemini_scores.novelty,
            "loopability": loopability,
        }
        avg = sum(scores.values()) / len(scores) if scores else 0

        scorecard_id = f"score_{ULID()}"
        scorecard = AggregateScorecard(
            id=scorecard_id,
            type="aggregate_scorecard",
            status="completed",
            created_at=now,
            updated_at=now,
            candidate_id=candidate.id,
            scores=scores,
            weighted_total=round(avg, 2),
        )

        return theory_eval, scorecard

    async def _gemini_evaluate(
        self,
        chord_symbols: list[str],
        genre: str,
        mood_targets: list[str],
        key: str,
        mode: str,
    ) -> GeminiScores:
        """Get Gemini Flash scores for soft dimensions."""
        rna = analyze_roman_numerals(key, mode, chord_symbols)
        rn_display = " → ".join(r.roman_numeral for r in rna)

        prompt = f"""Rate this chord progression on a 0-10 scale. Be critical and precise — avoid giving everything high scores. Differentiate between progressions.

Progression: {' → '.join(chord_symbols)}
Roman numerals: {rn_display}
Key: {key} {mode}
Target genre: {genre.replace('_', ' ')}
Target mood: {', '.join(mood_targets) if mood_targets else 'not specified'}

Score these dimensions (use the FULL 0-10 range, most scores should be 5-8):
- genre_fit: How authentically does this progression represent the target genre? Consider typical harmonic vocabulary, cadence patterns, and emotional quality. A generic progression that works in many genres should score 5-6, not 8+.
- emotional_fit: How well does it match the target mood? Consider the harmonic color, tension/release, and brightness/darkness.
- novelty: How creative or unexpected is this for the genre? Standard patterns = 3-4. Interesting twists = 6-7. Genuinely surprising but coherent = 8+."""

        try:
            return await self.gemini.generate_structured(
                prompt=prompt,
                response_model=GeminiScores,
                tier=ModelTier.FLASH,
                system_prompt="You are a professional music theory critic. Score honestly using the full range. Most progressions should score 5-7, not 8-10. Be discriminating.",
            )
        except Exception:
            return GeminiScores(genre_fit=6.0, emotional_fit=6.0, novelty=5.0)
