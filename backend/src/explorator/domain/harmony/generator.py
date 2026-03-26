"""Generate chord progressions using Gemini Pro + genre constraints."""

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.adapters.music21_adapter import analyze_roman_numerals
from explorator.models.harmony import ChordEvent, ProgressionCandidate, RomanNumeralAnalysis


class GeneratedProgression(BaseModel):
    """Schema for Gemini's structured output."""

    chord_symbols: list[str]
    rationale: str
    intent_tags: list[str] = Field(default_factory=list)


class GeneratedProgressionSet(BaseModel):
    """Multiple progressions from a single generation call."""

    progressions: list[GeneratedProgression]


def build_generation_prompt(
    genre: str,
    key_center: str,
    mode: str,
    bars: int,
    generation_mode: str,
    harmonic_vocabulary: list[str],
    common_devices: list[str],
    cadence_archetypes: list[str],
    mood_targets: list[str],
) -> str:
    """Build the prompt for Gemini Pro progression generation."""
    mode_instruction = {
        "conservative": "Stay close to genre archetypes. Prioritize genre fit and familiarity.",
        "balanced": "Mix archetypal progressions with moderately adventurous options.",
        "exploratory": "Push toward the edges of the genre's boundaries. Prioritize novelty.",
    }.get(generation_mode, "Mix archetypal and adventurous options.")

    return f"""Generate chord progressions for the following creative brief:

Genre: {genre.replace('_', ' ')}
Key: {key_center} {mode}
Length: {bars} bars (one chord per bar unless otherwise noted)
Mood: {', '.join(mood_targets) if mood_targets else 'not specified'}
Generation mode: {generation_mode} — {mode_instruction}

Genre harmonic vocabulary: {', '.join(harmonic_vocabulary)}
Common devices: {', '.join(common_devices)}
Cadence archetypes: {', '.join(cadence_archetypes)}

IMPORTANT constraints:
- Each progression must be exactly {bars} chords (one per bar)
- Use standard chord symbols (e.g., Cmaj7, Am7, Fmaj7, G7, Bbmaj7, Dm9)
- Progressions should LOOP well — the last chord should resolve naturally back to the first chord. This is critical for production use.
- Fit the genre and mood
- Include a rationale explaining the harmonic choices and why it loops well
- Include intent_tags (short descriptive words like "loopable", "dark", "ethereal")

Return multiple DISTINCT progressions. Vary the harmonic approach — don't just transpose the same idea."""


class HarmonyGenerator:
    """Generates chord progressions using Gemini Pro."""

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

    async def generate(
        self,
        session_id: str,
        genre: str,
        key_center: str,
        mode: str,
        bars: int,
        generation_mode: str,
        n_candidates: int,
        harmonic_vocabulary: list[str],
        common_devices: list[str],
        cadence_archetypes: list[str],
        mood_targets: list[str],
    ) -> list[ProgressionCandidate]:
        """Generate N progression candidates using Gemini Pro."""
        prompt = build_generation_prompt(
            genre=genre,
            key_center=key_center or "C",
            mode=mode or "major",
            bars=bars,
            generation_mode=generation_mode,
            harmonic_vocabulary=harmonic_vocabulary,
            common_devices=common_devices,
            cadence_archetypes=cadence_archetypes,
            mood_targets=mood_targets,
        )

        system_prompt = (
            f"You are a music theory expert specializing in {genre.replace('_', ' ')}. "
            f"Generate exactly {n_candidates} distinct chord progressions. "
            "Return valid JSON matching the schema."
        )

        result = await self.gemini.generate_structured(
            prompt=prompt,
            response_model=GeneratedProgressionSet,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        candidates: list[ProgressionCandidate] = []
        for prog in result.progressions[:n_candidates]:
            candidate_id = f"prog_{ULID()}"

            # Build chord events
            chord_events = [
                ChordEvent(
                    bar=i + 1,
                    beat=1.0,
                    duration_beats=4.0,
                    symbol=symbol,
                )
                for i, symbol in enumerate(prog.chord_symbols[:bars])
            ]

            # Analyze Roman numerals via music21
            rna_id = f"rna_{ULID()}"
            rn_results = analyze_roman_numerals(
                key=key_center or "C",
                mode=mode or "major",
                chord_symbols=prog.chord_symbols[:bars],
            )
            rna = RomanNumeralAnalysis(
                id=rna_id,
                type="roman_numeral_analysis",
                status="completed",
                progression_candidate_id=candidate_id,
                analysis_events=[
                    {"bar": i + 1, "symbol": r.roman_numeral, "confidence": r.confidence}
                    for i, r in enumerate(rn_results)
                ],
            )

            candidate = ProgressionCandidate(
                id=candidate_id,
                type="progression_candidate",
                status="candidate",
                session_id=session_id,
                rationale=prog.rationale,
                intent_tags=prog.intent_tags,
                key_center=key_center or "C",
                mode=mode or "major",
                phrase_length_bars=bars,
                chord_events=chord_events,
                roman_numeral_analysis_id=rna_id,
                generator_mode=generation_mode,
                source_type="generated",
            )

            # Attach RNA as metadata for now (persisted in persist_round)
            candidate.metadata["roman_numeral_analysis"] = rna.model_dump(mode="json")
            candidates.append(candidate)

        return candidates
