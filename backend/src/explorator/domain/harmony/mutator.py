"""Harmony mutation service — Gemini Pro with constrained vocabulary."""

import logging

from pydantic import BaseModel, Field

from explorator.adapters.llm import LLMClient, ModelTier
from explorator.prompts.mutation import mutation_prompt

logger = logging.getLogger(__name__)

HARMONIC_OPS = [
    "substitute_chord",
    "reharmonize_cadence",
    "modal_interchange",
    "alter_density",
    "experimental",
]
ARRANGEMENT_OPS = ["swap_voicing_type", "swap_bass_mode", "shift_register", "experimental"]


class MutationResponseItem(BaseModel):
    """One mutation within a response."""

    operation: str
    position: int = -1  # chord index affected (-1 if N/A)
    original_value: str = ""  # what was there before
    new_value: str = ""  # what it was changed to
    description: str = ""  # free-form description of the change
    reason: str = ""
    predicted_score_changes: list[str] = Field(default_factory=list)  # e.g. ["novelty: +1.0"]


class MutationResponse(BaseModel):
    """Gemini Pro structured response for mutation."""

    mutated_chord_symbols: list[str]
    mutations: list[MutationResponseItem] = Field(default_factory=list)


class HarmonyMutator:
    """Mutates chord progressions using Gemini Pro with constrained vocabulary."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def mutate_harmonic(
        self,
        chord_symbols: list[str],
        genre: str,
        scores: dict[str, float],
        guidance: str | None = None,
    ) -> MutationResponse:
        """Apply harmonic mutations to a chord progression.

        Uses Gemini Pro to select and apply mutations from the constrained
        vocabulary. At most 1 experimental mutation is kept per call.
        """
        user_prompt, system_prompt = mutation_prompt(
            chord_symbols=chord_symbols,
            genre=genre,
            scores=scores,
            guidance=guidance,
            allowed_operations=HARMONIC_OPS,
        )

        response = await self.llm.generate_structured(
            prompt=user_prompt,
            response_model=MutationResponse,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        response = self._cap_experimental(response)
        response = self._ensure_length(response, chord_symbols)
        return response

    def _ensure_length(self, response: MutationResponse, original: list[str]) -> MutationResponse:
        """Ensure mutated progression has same length as original. Pad with originals if too short."""  # noqa: E501
        mutated = list(response.mutated_chord_symbols)
        if len(mutated) < len(original):
            logger.warning(
                "Gemini returned %d chords, expected %d — padding with originals",
                len(mutated),
                len(original),
            )
            mutated.extend(original[len(mutated) :])
        return MutationResponse(
            mutated_chord_symbols=mutated[: len(original)],
            mutations=response.mutations,
        )

    def _cap_experimental(self, response: MutationResponse) -> MutationResponse:
        """Keep at most 1 experimental mutation."""
        seen_experimental = False
        filtered: list[MutationResponseItem] = []
        for m in response.mutations:
            if m.operation == "experimental":
                if seen_experimental:
                    continue
                seen_experimental = True
            filtered.append(m)
        return MutationResponse(
            mutated_chord_symbols=response.mutated_chord_symbols,
            mutations=filtered,
        )
