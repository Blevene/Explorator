"""Fake Gemini client for E2E testing — returns deterministic structured responses."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TypeVar

from pydantic import BaseModel

from explorator.adapters.gemini import ModelTier

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Lazy-initialized fixture map (avoids circular imports at module level)
_BUILDERS: dict[str, object] = {}


def _get_builders() -> dict:
    """Build fixture map on first call."""
    if _BUILDERS:
        return _BUILDERS

    from explorator.domain.intent.parser import SoftPreferences
    from explorator.domain.harmony.generator import GeneratedProgression, GeneratedProgressionSet
    from explorator.domain.evaluation.theory import GeminiScores
    from explorator.models.realization import ChordVoicingInstruction, VoicingStrategyResponse
    from explorator.domain.harmony.mutator import MutationResponse, MutationResponseItem
    from explorator.domain.intent.feedback import FeedbackInterpretation

    _PROGS = [
        GeneratedProgression(
            chord_symbols=["Amaj7", "F#m7", "Dmaj7", "E7"],
            rationale="Classic dream pop I-vi-IV-V with 7th extensions",
            intent_tags=["wistful", "ethereal"],
        ),
        GeneratedProgression(
            chord_symbols=["Amaj7", "C#m7", "F#m7", "Dmaj7"],
            rationale="Descending through relative minor",
            intent_tags=["melancholic", "flowing"],
        ),
        GeneratedProgression(
            chord_symbols=["Dmaj7", "Amaj7", "E7", "F#m7"],
            rationale="Subdominant-start for floating quality",
            intent_tags=["dreamy", "open"],
        ),
        GeneratedProgression(
            chord_symbols=["F#m7", "Dmaj7", "Amaj7", "E7"],
            rationale="Minor-start for darker mood",
            intent_tags=["haunted", "atmospheric"],
        ),
    ]

    _BUILDERS.update({
        "SoftPreferences": lambda: SoftPreferences(
            mood_targets=["wistful", "ethereal"],
            energy_level="low",
            complexity_target="medium",
            novelty_target="moderate",
        ),
        "GeneratedProgressionSet": lambda: GeneratedProgressionSet(progressions=_PROGS),
        "GeminiScores": lambda: GeminiScores(genre_fit=7.5, emotional_fit=7.0, novelty=6.5),
        "VoicingStrategyResponse": lambda: VoicingStrategyResponse(
            global_strategy="Open voicings with 7th extensions",
            density_level="medium",
            voice_count=4,
            register_profile="mid_high",
            rationale="Ethereal spread voicings",
            per_chord=[
                ChordVoicingInstruction(
                    chord_symbol=sym, voicing_type="open",
                    target_register="mid_high", extensions_to_include=["7"],
                )
                for sym in ["Amaj7", "F#m7", "Dmaj7", "E7"]
            ],
        ),
        "MutationResponse": lambda: MutationResponse(
            mutated_chord_symbols=["Amaj7", "F#m9", "Dmaj7", "Esus4"],
            mutations=[MutationResponseItem(
                operation="substitute_chord", position=1,
                original_value="F#m7", new_value="F#m9",
                description="Added 9th for color", reason="Increases novelty",
                predicted_score_changes=["novelty: +0.5"],
            )],
        ),
        "FeedbackInterpretation": lambda: FeedbackInterpretation(
            interpreted_adjustments={"increase_novelty": True, "reduce_predictability": True},
            weight_deltas={"novelty": 0.03, "genre_fit": -0.02, "loopability": -0.01},
            satisfaction="neutral",
        ),
    })
    return _BUILDERS


class FakeGeminiClient:
    """Drop-in replacement for GeminiClient returning deterministic fixtures."""

    def __init__(self) -> None:
        self.call_counts: dict[str, int] = defaultdict(int)

    def get_model_name(self, tier: ModelTier) -> str:
        return f"fake-{tier.value}"

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> T:
        """Return a deterministic fixture based on response_model type."""
        name = response_model.__name__
        builders = _get_builders()
        if name not in builders:
            msg = f"Unsupported response_model for FakeGeminiClient: {name}"
            raise ValueError(msg)
        self.call_counts[name] += 1
        logger.info("FakeGemini: %s (call #%d)", name, self.call_counts[name])
        return builders[name]()

    async def generate_text(
        self,
        prompt: str,
        tier: ModelTier = ModelTier.FLASH,
        system_prompt: str | None = None,
    ) -> str:
        self.call_counts["generate_text"] += 1
        return "Mock text response"
