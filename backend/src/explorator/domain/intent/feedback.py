"""Feedback interpretation — Gemini Flash translates user text to weight deltas."""

import asyncio
import logging

from pydantic import BaseModel, Field

from explorator.adapters.llm import LLMClient, ModelTier
from explorator.prompts.feedback import feedback_interpretation_prompt

logger = logging.getLogger(__name__)

# Clamp bounds for any single weight dimension
_WEIGHT_MIN = 0.02
_WEIGHT_MAX = 0.50
_INTERPRET_TIMEOUT_SECONDS = 15


class FeedbackInterpretation(BaseModel):
    """Gemini Flash structured response for feedback interpretation."""

    interpreted_adjustments: dict[str, object] = Field(default_factory=dict)
    weight_deltas: dict[str, float] = Field(default_factory=dict)
    satisfaction: str = "neutral"  # "positive" | "neutral" | "negative"


def apply_weight_deltas(
    current_weights: dict[str, float],
    deltas: dict[str, float],
) -> dict[str, float]:
    """Apply deltas, clamp to [_WEIGHT_MIN, _WEIGHT_MAX], renormalize to sum 1.0.

    Uses iterative clamp-then-renorm to ensure bounds are preserved after
    renormalization. Converges in a small number of iterations for typical inputs.
    """
    result = dict(current_weights)
    for dim, delta in deltas.items():
        if dim in result:
            result[dim] = result[dim] + delta
        else:
            logger.warning("apply_weight_deltas: unknown dimension %r — delta ignored", dim)

    # Iterative clamp + renorm until stable (bounds survive renormalization)
    for _ in range(50):
        # Clamp each dimension to [_WEIGHT_MIN, _WEIGHT_MAX]
        for dim in result:
            result[dim] = max(_WEIGHT_MIN, min(_WEIGHT_MAX, result[dim]))
        # Renormalize to sum 1.0
        total = sum(result.values())
        if total <= 0:
            break
        prev = dict(result)
        for dim in result:
            result[dim] = result[dim] / total
        # Check convergence
        if all(abs(result[d] - prev[d]) < 1e-9 for d in result):
            break

    # Final round to 4 decimal places
    for dim in result:
        result[dim] = round(result[dim], 4)

    return result


class FeedbackInterpreter:
    """Interprets user feedback text into weight adjustments using Gemini Flash."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def interpret(
        self,
        feedback_text: str,
        current_weights: dict[str, float],
        candidate_scores: dict[str, float],
        genre: str,
    ) -> FeedbackInterpretation:
        """Interpret feedback text into weight deltas via Gemini Flash."""
        user_prompt, system_prompt = feedback_interpretation_prompt(
            feedback_text=feedback_text,
            current_weights=current_weights,
            candidate_scores=candidate_scores,
            genre=genre,
        )

        result = await asyncio.wait_for(
            self.llm.generate_structured(
                prompt=user_prompt,
                response_model=FeedbackInterpretation,
                tier=ModelTier.FLASH,
                system_prompt=system_prompt,
            ),
            timeout=_INTERPRET_TIMEOUT_SECONDS,
        )

        return result
