"""Theory evaluation — deterministic checks + Gemini hybrid scoring.

Deterministic checks run first. Gemini Flash scores softer dimensions.
LLM is never the sole scoring authority.
"""

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.adapters.music21_adapter import parse_chord_symbol
from explorator.models.evaluation import AggregateScorecard, TheoryEvaluation
from explorator.models.harmony import ProgressionCandidate
from explorator.utils import utc_now


def check_loopability(chord_symbols: list[str]) -> float:
    """Score how well a progression loops (0-10). Same start/end = high score."""
    if not chord_symbols:
        return 5.0
    if chord_symbols[0] == chord_symbols[-1]:
        return 9.0
    # Check if roots are the same even with different extensions
    first = parse_chord_symbol(chord_symbols[0])
    last = parse_chord_symbol(chord_symbols[-1])
    if first.root == last.root:
        return 8.0
    return 5.5


def check_cadence_quality(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score cadence quality based on the last two chords (0-10)."""
    if len(chord_symbols) < 2:
        return 5.0

    last = parse_chord_symbol(chord_symbols[-1])
    penult = parse_chord_symbol(chord_symbols[-2])

    # V-I or V-i is a strong cadence
    if last.root == key and penult.root is not None:
        return 8.5

    # IV-I plagal cadence
    return 6.5


def check_theoretical_coherence(
    chord_symbols: list[str], key: str, mode: str
) -> float:
    """Score how well chords fit the key (0-10). More diatonic = higher."""
    if not chord_symbols:
        return 5.0

    # Simple heuristic: count how many chords parse successfully
    parsed = [parse_chord_symbol(s) for s in chord_symbols]
    valid = sum(1 for p in parsed if p.root != "unknown")
    ratio = valid / len(chord_symbols) if chord_symbols else 0
    return 5.0 + (ratio * 5.0)  # 5-10 range


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
        prompt = f"""Rate this chord progression on a scale of 0-10:

Progression: {' → '.join(chord_symbols)}
Key: {key} {mode}
Target genre: {genre.replace('_', ' ')}
Target mood: {', '.join(mood_targets) if mood_targets else 'not specified'}

Score these dimensions:
- genre_fit: How well does this progression fit the target genre? (0-10)
- emotional_fit: How well does it match the target mood? (0-10)
- novelty: How creative/unexpected is this progression for the genre? (0-10)"""

        try:
            return await self.gemini.generate_structured(
                prompt=prompt,
                response_model=GeminiScores,
                tier=ModelTier.FLASH,
                system_prompt="You are a music theory critic. Score honestly and precisely.",
            )
        except Exception:
            # Fallback: neutral scores if Gemini fails
            return GeminiScores(genre_fit=6.0, emotional_fit=6.0, novelty=5.0)
