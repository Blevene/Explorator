"""Generate chord progressions using the pro-tier LLM + genre constraints."""

from pydantic import BaseModel, Field
from ulid import ULID

from explorator.adapters.llm import LLMClient, ModelTier
from explorator.adapters.music21_adapter import analyze_roman_numerals
from explorator.models.harmony import (
    ChordEvent,
    ProgressionCandidate,
    RomanNumeralAnalysis,
)
from explorator.prompts.generation import progression_generation_prompt
from explorator.utils import utc_now


class GeneratedProgression(BaseModel):
    """Schema for LLM's structured output."""

    chord_symbols: list[str]
    rationale: str
    intent_tags: list[str] = Field(default_factory=list)


class GeneratedProgressionSet(BaseModel):
    """Multiple progressions from a single generation call."""

    progressions: list[GeneratedProgression]


class HarmonyGenerator:
    """Generates chord progressions using the pro-tier LLM."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

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
        """Generate N progression candidates using the pro-tier LLM."""
        prompt, system_prompt = progression_generation_prompt(
            genre=genre,
            key_center=key_center or "C",
            mode=mode or "major",
            bars=bars,
            generation_mode=generation_mode,
            n_candidates=n_candidates,
            harmonic_vocabulary=harmonic_vocabulary,
            common_devices=common_devices,
            cadence_archetypes=cadence_archetypes,
            mood_targets=mood_targets,
        )

        result = await self.llm.generate_structured(
            prompt=prompt,
            response_model=GeneratedProgressionSet,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        candidates: list[ProgressionCandidate] = []
        for prog in result.progressions[:n_candidates]:
            candidate_id = f"prog_{ULID()}"

            chord_events = [
                ChordEvent(
                    bar=i + 1,
                    beat=1.0,
                    duration_beats=4.0,
                    symbol=symbol,
                )
                for i, symbol in enumerate(prog.chord_symbols[:bars])
            ]

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
                    {
                        "bar": i + 1,
                        "symbol": r.roman_numeral,
                        "confidence": r.confidence,
                    }
                    for i, r in enumerate(rn_results)
                ],
            )

            now = utc_now()
            candidate = ProgressionCandidate(
                id=candidate_id,
                type="progression_candidate",
                status="candidate",
                created_at=now,
                updated_at=now,
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

            candidate.metadata["roman_numeral_analysis"] = rna.model_dump(
                mode="json"
            )
            candidates.append(candidate)

        return candidates
