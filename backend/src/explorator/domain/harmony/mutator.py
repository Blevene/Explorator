"""Harmony mutation service — Gemini Pro with constrained vocabulary."""

import logging

from pydantic import BaseModel, Field

from explorator.adapters.gemini import GeminiClient, ModelTier
from explorator.prompts.mutation import MUTATION_OPERATIONS, mutation_prompt

logger = logging.getLogger(__name__)

HARMONIC_OPS = ["substitute_chord", "reharmonize_cadence", "modal_interchange", "alter_density", "experimental"]
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

    def __init__(self, gemini: GeminiClient) -> None:
        self.gemini = gemini

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

        response = await self.gemini.generate_structured(
            prompt=user_prompt,
            response_model=MutationResponse,
            tier=ModelTier.PRO,
            system_prompt=system_prompt,
        )

        response = self._cap_experimental(response)
        return response

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
